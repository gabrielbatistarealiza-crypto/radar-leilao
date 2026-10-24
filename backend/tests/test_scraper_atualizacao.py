"""Atualização da lista da Caixa (ScraperService.atualizar_lista_caixa).

Não baixa nada e não abre navegador: o downloader e o scraper são trocados
por versões falsas que devolvem listas prontas.
"""
import pytest

from app.models.atualizacao_caixa import AtualizacaoCaixa
from app.models.imovel import Imovel, ImovelImagem
from app.models.oportunidade import Oportunidade
from app.schemas.imovel_scraper import ImovelScraper
from app.services import scraper_service
from app.services.caixa_downloader import CaixaDownloader
from app.services.scraper_service import ScraperService

URL = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"
TODAS_AS_UFS = list(CaixaDownloader.UFS)


def dto(numero, **extra):
    base = dict(
        titulo=f"Imóvel {numero}",
        url=URL.format(numero),
        cidade="Campinas",
        estado="SP",
        valor_avaliacao=200000.0,
        valor_leilao=100000.0,
        modalidade="Leilão SFI - Edital Único",
        fonte="Caixa",
    )
    base.update(extra)
    return ImovelScraper(**base)


class ListaQueFalha(list):
    """Simula um erro ao salvar as fotos: quebra quando o serviço a percorre."""

    def __bool__(self):
        return True

    def __iter__(self):
        raise RuntimeError("falha simulada ao salvar")


@pytest.fixture()
def rodar(monkeypatch, sessao):
    """Roda atualizar_lista_caixa com a lista da Caixa e os estados dados."""

    def _rodar(dtos, estados_baixados=None, erro_no_download=None):
        sucesso = TODAS_AS_UFS if estados_baixados is None else estados_baixados

        class DownloaderFalso:
            UFS = TODAS_AS_UFS

            def baixar_todos(self, *args, **kwargs):
                if erro_no_download:
                    raise erro_no_download
                return {"sucesso": list(sucesso), "falhas": []}

        class ScraperFalso:
            def executar(self):
                return list(dtos)

        monkeypatch.setattr(scraper_service, "CaixaDownloader", DownloaderFalso)
        monkeypatch.setattr(scraper_service, "CaixaScraper", ScraperFalso)
        monkeypatch.setattr(
            ScraperService, "preparar_fila_fotos_caixa", lambda self, imoveis: {"pendentes": 0}
        )
        return ScraperService(sessao).atualizar_lista_caixa()

    return _rodar


def existe(sessao, numero):
    return sessao.query(Imovel).filter(Imovel.url == URL.format(numero)).first() is not None


# ------------------------------------------------------------ importação

def test_cria_os_novos_e_atualiza_os_existentes(rodar, sessao, fabrica):
    fabrica.imovel(titulo="Antigo", url=URL.format(1), fonte="Caixa", valor_leilao=500.0)
    resultado = rodar([dto(1, valor_leilao=90000.0), dto(2)])

    assert resultado["imoveis_atualizados"] == 2
    assert resultado["imoveis_removidos"] == 0
    assert sessao.query(Imovel).count() == 2
    atualizado = sessao.query(Imovel).filter(Imovel.url == URL.format(1)).one()
    assert atualizado.valor_leilao == pytest.approx(90000.0)


def test_normaliza_a_url_pelo_numero_do_imovel(rodar, sessao):
    rodar([dto(7, url="https://venda-imoveis.caixa.gov.br/x.asp?foo=1&HDNIMOVEL=7&bar=2")])
    assert existe(sessao, 7)


def test_nao_apaga_campos_com_valor_ausente_no_csv(rodar, sessao, fabrica):
    fabrica.imovel(url=URL.format(1), fonte="Caixa", area=80.0, quartos=3)
    rodar([dto(1)])  # o CSV novo não traz área nem quartos
    imovel = sessao.query(Imovel).filter(Imovel.url == URL.format(1)).one()
    assert imovel.area == pytest.approx(80.0)
    assert imovel.quartos == 3


def test_salva_as_fotos_do_csv_sem_duplicar(rodar, sessao):
    rodar([dto(1, imagens=["http://x/a.jpg", "http://x/b.jpg"])])
    rodar([dto(1, imagens=["http://x/a.jpg", "http://x/b.jpg"])])
    assert sessao.query(ImovelImagem).count() == 2


# -------------------------------------------------------------- remoção

def test_remove_imovel_que_saiu_da_lista(rodar, sessao, fabrica):
    saiu = fabrica.imovel(url=URL.format(3), fonte="Caixa")
    fabrica.foto(saiu, "http://x/foto.jpg")

    resultado = rodar([dto(1)])

    assert resultado["imoveis_removidos"] == 1
    assert not existe(sessao, 3)
    assert sessao.query(ImovelImagem).count() == 0  # fotos saem junto


def test_preserva_imovel_ausente_que_tem_oportunidade(rodar, sessao, fabrica, cliente):
    imovel = fabrica.imovel(url=URL.format(4), fonte="Caixa")
    fabrica.oportunidade(cliente, imovel)

    resultado = rodar([dto(1)])

    assert resultado["imoveis_removidos"] == 0
    assert existe(sessao, 4)
    assert sessao.query(Oportunidade).count() == 1


def test_download_parcial_nao_remove_nada(rodar, sessao, fabrica):
    fabrica.imovel(url=URL.format(3), fonte="Caixa")
    resultado = rodar([dto(1)], estados_baixados=TODAS_AS_UFS[:-1])
    assert resultado["imoveis_removidos"] == 0
    assert existe(sessao, 3)


def test_lista_vazia_nao_remove_nada(rodar, sessao, fabrica):
    fabrica.imovel(url=URL.format(3), fonte="Caixa")
    resultado = rodar([])
    assert resultado["imoveis_removidos"] == 0
    assert existe(sessao, 3)


def test_nao_mexe_em_imoveis_de_outras_fontes(rodar, sessao, fabrica):
    fabrica.imovel(url="http://outra-fonte/1", fonte="Outra Fonte")
    fabrica.imovel(url=None, fonte="Caixa")
    resultado = rodar([dto(1)])
    assert resultado["imoveis_removidos"] == 0
    assert sessao.query(Imovel).count() == 3


def test_imovel_que_falha_ao_salvar_mas_esta_no_csv_nao_e_removido(rodar, sessao, fabrica):
    # Antes da correção, o imóvel cujo salvamento falhava ficava fora da lista
    # de "ativos" e era apagado, mesmo estando no CSV da Caixa.
    fabrica.imovel(titulo="Vai falhar", url=URL.format(5), fonte="Caixa")
    quebrado = ImovelScraper.model_construct(
        titulo="Vai falhar", url=URL.format(5), fonte="Caixa", imagens=ListaQueFalha()
    )

    resultado = rodar([dto(1), quebrado])

    assert resultado["imoveis_removidos"] == 0
    assert existe(sessao, 5)


# ------------------------------------------------------------- registro

def test_registra_a_execucao_como_concluida(rodar, sessao, fabrica):
    fabrica.imovel(url=URL.format(3), fonte="Caixa")
    rodar([dto(1), dto(2)])

    registro = sessao.query(AtualizacaoCaixa).one()
    assert registro.status == "CONCLUIDA"
    assert registro.imoveis_atualizados == 2
    assert registro.imoveis_removidos == 1
    assert registro.estados_baixados == len(TODAS_AS_UFS)
    assert registro.concluida_em is not None
    assert registro.erro is None


def test_falha_no_download_marca_a_execucao_como_erro(rodar, sessao):
    with pytest.raises(RuntimeError, match="CAPTCHA"):
        rodar([dto(1)], erro_no_download=RuntimeError("CAPTCHA/bloqueio do Radware"))

    registro = sessao.query(AtualizacaoCaixa).one()
    assert registro.status == "ERRO"
    assert "CAPTCHA" in registro.erro
    assert sessao.query(Imovel).count() == 0


# ------------------------------------------------------- financiamento

def buscar_imovel(sessao, numero):
    return sessao.query(Imovel).filter(Imovel.url == URL.format(numero)).one()


def test_grava_e_atualiza_aceita_financiamento(rodar, sessao):
    rodar([dto(1, aceita_financiamento=True)])
    assert buscar_imovel(sessao, 1).aceita_financiamento is True

    # False é um dado real ("não aceita") e precisa ser gravado.
    rodar([dto(1, aceita_financiamento=False)])
    assert buscar_imovel(sessao, 1).aceita_financiamento is False


def test_financiamento_ausente_no_csv_nao_apaga_o_valor_conhecido(rodar, sessao, fabrica):
    fabrica.imovel(url=URL.format(1), fonte="Caixa", aceita_financiamento=True)
    rodar([dto(1)])  # esta linha do CSV não informou financiamento
    assert buscar_imovel(sessao, 1).aceita_financiamento is True
