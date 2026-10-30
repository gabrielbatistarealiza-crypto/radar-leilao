"""Fase 3: imóveis fora da lista (sem apagar) e histórico de eventos. Sem rede."""
import pytest

from app.models.imovel import Imovel, ImovelEvento
from app.schemas.imovel_scraper import ImovelScraper
from app.services import scraper_service
from app.services.caixa_downloader import CaixaDownloader
from app.services.scraper_service import ScraperService

URL = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"
TODAS = list(CaixaDownloader.UFS)


def dto(numero, **extra):
    base = dict(titulo=f"Imóvel {numero}", url=URL.format(numero), cidade="Campinas", estado="SP",
                valor_avaliacao=200000.0, valor_leilao=100000.0, fonte="Caixa")
    base.update(extra)
    return ImovelScraper(**base)


@pytest.fixture()
def rodar(monkeypatch, sessao):
    def _rodar(dtos, estados=None, remover=True):
        sucesso = TODAS if estados is None else estados

        class DownloaderFalso:
            UFS = TODAS

            def baixar_todos(self, *args, **kwargs):
                return {"sucesso": list(sucesso), "falhas": []}

        class ScraperFalso:
            def __init__(self):
                self.ufs_permitidas = None

            def executar(self):
                return list(dtos)

        monkeypatch.setattr(scraper_service, "CaixaDownloader", DownloaderFalso)
        monkeypatch.setattr(scraper_service, "CaixaScraper", ScraperFalso)
        monkeypatch.setattr(ScraperService, "preparar_fila_fotos_caixa", lambda self, i: {"pendentes": 0})
        r = ScraperService(sessao).atualizar_lista_caixa(remover=remover)
        sessao.expire_all()
        return r

    return _rodar


def eventos(sessao, imovel_id=None):
    consulta = sessao.query(ImovelEvento)
    if imovel_id is not None:
        consulta = consulta.filter(ImovelEvento.imovel_id == imovel_id)
    return [(e.tipo, e.valor_anterior, e.valor_novo) for e in consulta.order_by(ImovelEvento.id)]


def por_numero(sessao, numero):
    return sessao.query(Imovel).filter(Imovel.url == URL.format(numero)).one()


def test_imovel_novo_entra_na_lista_com_evento_e_visto(rodar, sessao):
    rodar([dto(1)])

    imovel = por_numero(sessao, 1)
    assert imovel.na_lista is True and imovel.visto_na_lista_em is not None
    assert eventos(sessao, imovel.id) == [(ImovelEvento.ENTROU, None, 100000.0)]


def test_ausente_sai_da_lista_com_evento_e_volta_quando_reaparece(rodar, sessao, fabrica):
    antigo = fabrica.imovel(url=URL.format(7), fonte="Caixa", valor_leilao=100000.0)

    r = rodar([dto(1)])
    assert r["imoveis_removidos"] == 1 and r["ausentes_da_lista"] == 1
    fora = sessao.get(Imovel, antigo.id)
    assert fora.na_lista is False and fora.saiu_da_lista_em is not None
    assert eventos(sessao, antigo.id) == [(ImovelEvento.SAIU, None, None)]

    rodar([dto(1), dto(7)])
    voltou = sessao.get(Imovel, antigo.id)
    assert voltou.na_lista is True and voltou.saiu_da_lista_em is None
    assert eventos(sessao, antigo.id)[-1] == (ImovelEvento.VOLTOU, None, None)


def test_mudanca_de_preco_fica_no_historico(rodar, sessao, fabrica):
    imovel = fabrica.imovel(url=URL.format(1), fonte="Caixa", valor_leilao=150000.0)

    rodar([dto(1, valor_leilao=120000.0)])
    rodar([dto(1, valor_leilao=120000.0)])  # sem mudança: nada novo

    assert eventos(sessao, imovel.id) == [(ImovelEvento.PRECO, 150000.0, 120000.0)]
    assert sessao.get(Imovel, imovel.id).valor_leilao == pytest.approx(120000.0)


def test_quem_ja_esta_fora_nao_volta_a_contar_como_ausente(rodar, sessao, fabrica):
    fabrica.imovel(url=URL.format(7), fonte="Caixa")
    rodar([dto(1)])
    r = rodar([dto(1)])

    assert r["ausentes_da_lista"] == 0 and r["imoveis_removidos"] == 0
    assert [t for t, _, _ in eventos(sessao)].count(ImovelEvento.SAIU) == 1


def test_sem_remover_so_conta_os_ausentes(rodar, sessao, fabrica):
    antigo = fabrica.imovel(url=URL.format(7), fonte="Caixa")

    r = rodar([dto(1)], remover=False)

    assert r["ausentes_da_lista"] == 1 and r["imoveis_removidos"] == 0
    assert sessao.get(Imovel, antigo.id).na_lista is True


def test_descarga_parcial_nao_tira_ninguem_da_lista(rodar, sessao, fabrica):
    antigo = fabrica.imovel(url=URL.format(7), fonte="Caixa")

    r = rodar([dto(1)], estados=TODAS[:5])

    assert r["imoveis_removidos"] == 0 and r["ausentes_da_lista"] is None
    assert sessao.get(Imovel, antigo.id).na_lista is True


def test_ausentes_acima_do_limite_sao_recusados_sem_marcar(rodar, sessao, fabrica, monkeypatch):
    monkeypatch.setattr(ScraperService, "LIMITE_REMOCAO_MINIMO", 1)
    for n in range(10, 13):
        fabrica.imovel(url=URL.format(n), fonte="Caixa")

    r = rodar([dto(1)])  # 3 ausentes em 4 na lista: acima de max(1, 20%)

    assert r["remocao_recusada"] == 3 and r["imoveis_removidos"] == 0
    assert sessao.query(Imovel).filter(Imovel.na_lista.is_(False)).count() == 0


def test_outras_fontes_nunca_saem_da_lista(rodar, sessao, fabrica):
    outro = fabrica.imovel(url="http://outra-fonte/1", fonte="Outra Fonte")
    rodar([dto(1)])
    assert sessao.get(Imovel, outro.id).na_lista is True
