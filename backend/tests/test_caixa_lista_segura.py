"""Descarga segura das listas da CAIXA e a importação que a usa.

Sem rede: o pedido HTTP é trocado por respostas prontas; os CSV são escritos
numa pasta temporária. A base é a de teste do conftest.
"""
from datetime import datetime

import pytest

from app.models.caixa_data_worker_state import CaixaDataWorkerState
from app.models.imovel import Imovel
from app.schemas.imovel_scraper import ImovelScraper
from app.services import caixa_datas_edital as ce
from app.services import caixa_lista_segura as cl
from app.services import scraper_service
from app.services.caixa_datas_edital import RespostaCaixa
from app.services.scraper_service import ScraperService

URL = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"


def csv_caixa(uf, geracao="27/10/2026"):
    return (
        f" Lista de Imóveis da Caixa;;Data de geração:;{geracao};;;;;;;\n"
        " N° do imóvel;UF;Cidade;Bairro;Endereço;Preço;Valor de avaliação;Desconto;"
        "Financiamento;Descrição;Modalidade de venda;Link de acesso\n"
        f"8444408241749;{uf};CIDADE;BAIRRO;RUA X;100.000,00;150.000,00;33,33;Sim;Casa;"
        f"Leilão SFI - Edital Único;{URL.format('8444408241749')}\n"
    ).encode("cp1252")


class Rede:
    def __init__(self, respostas=None, padrao=None):
        self.respostas, self.padrao, self.pedidos = respostas or {}, padrao, []

    def __call__(self, url, tipo):
        self.pedidos.append((url, tipo))
        uf = url.rsplit("_", 1)[1][:2]
        r = self.respostas.get(uf, self.padrao)
        if r is None:
            r = csv_caixa(uf)
        return r if isinstance(r, RespostaCaixa) else RespostaCaixa("OK", status=200, corpo=r)


def baixador(tmp_path, rede, pausas=None):
    return cl.CaixaListaSegura(pasta_dados=tmp_path, pedir=rede,
                               dormir=(pausas.append if pausas is not None else (lambda s: None)),
                               intervalo=60)


# ------------------------------------------------------------- descarga

def test_descarrega_as_27_ufs_com_pausa_e_um_pedido_cada(tmp_path):
    rede, pausas = Rede(), []
    r = baixador(tmp_path, rede, pausas).baixar_todos()

    assert r["sucesso"] == cl.CaixaListaSegura.UFS and r["bloqueado"] is False
    assert r["pedidos"] == 27 and len(rede.pedidos) == 27
    assert all(tipo == "lista" for _, tipo in rede.pedidos)
    assert rede.pedidos[0][0] == "https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_AC.csv"
    assert pausas == [60] * 26
    assert set(r["geracoes"].values()) == {"2026-10-27"}
    assert len(list(tmp_path.glob("Lista_imoveis_*.csv"))) == 27


def test_max_ufs_limita_os_pedidos(tmp_path):
    rede = Rede()
    r = baixador(tmp_path, rede).baixar_todos(max_ufs=2)
    assert r["sucesso"] == ["AC", "AL"] and len(rede.pedidos) == 2


@pytest.mark.parametrize("resposta, motivo", [
    (RespostaCaixa("REDIRECIONADO", status=302, destino="validate.perfdrive.com"), "REDIRECIONADO"),
    (RespostaCaixa("BLOQUEADO_HTTP_403", status=403), "BLOQUEADO_HTTP_403"),
    (RespostaCaixa("BLOQUEADO_HTTP_429", status=429), "BLOQUEADO_HTTP_429"),
    (RespostaCaixa("BLOQUEADO", status=200), "BLOQUEADO"),
    (RespostaCaixa("TIMEOUT_LIGACAO"), "TIMEOUT_LIGACAO"),
    (b"<html><body>Pagina de erro</body></html>", "NAO_E_CSV_DA_CAIXA"),
    (b"Lista de Imoveis;sem data de geracao\nUF;Cidade;Link de acesso\n", "NAO_E_CSV_DA_CAIXA"),
])
def test_qualquer_anomalia_para_a_descarga_e_preserva_o_csv_anterior(tmp_path, resposta, motivo):
    (tmp_path / "Lista_imoveis_AP.csv").write_bytes(csv_caixa("AP", "01/10/2026"))
    rede = Rede({"AP": resposta})

    r = baixador(tmp_path, rede).baixar_todos()

    assert r["bloqueado"] is True and r["paragem"] == motivo and r["uf_bloqueada"] == "AP"
    assert r["sucesso"] == ["AC", "AL"] and len(rede.pedidos) == 3  # nada depois do AP
    assert (tmp_path / "Lista_imoveis_AP.csv").read_bytes() == csv_caixa("AP", "01/10/2026")


def test_csv_anterior_fica_em_reserva(tmp_path):
    (tmp_path / "Lista_imoveis_AC.csv").write_bytes(csv_caixa("AC", "01/10/2026"))
    baixador(tmp_path, Rede()).baixar_todos(max_ufs=1)
    assert (tmp_path / "_anterior" / "Lista_imoveis_AC.csv").read_bytes() == csv_caixa("AC", "01/10/2026")
    assert cl.data_de_geracao((tmp_path / "Lista_imoveis_AC.csv").read_bytes()).isoformat() == "2026-10-27"
    assert not list(tmp_path.glob(".*.tmp"))


def test_url_da_lista_permitido_e_outros_recusados():
    assert ce.url_permitido("https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_SP.csv", "lista")
    for url in ("https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_SP.csv?x=1",
                "https://venda-imoveis.caixa.gov.br/listaweb/../sistema/x.csv",
                "https://outro.gov.br/listaweb/Lista_imoveis_SP.csv",
                "http://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_SP.csv"):
        assert not ce.url_permitido(url, "lista")


def test_pedido_da_lista_com_302_nao_le_o_corpo():
    class Resposta:
        status_code, headers, lidos = 302, {"Location": "https://validate.perfdrive.com/a"}, 0

        def iter_content(self, n):
            Resposta.lidos += 1
            yield b"x"

        def close(self):
            pass

    class Sessao:
        trust_env = True

        def get(self, url, **kw):
            assert kw["allow_redirects"] is False and kw["stream"] is True and self.trust_env is False
            return Resposta()

        def close(self):
            pass

    r = ce.pedir_caixa("https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_SP.csv", "lista",
                       sessao_factory=Sessao)
    assert r.veredicto == "REDIRECIONADO" and Resposta.lidos == 0


# ------------------------------------------------------------- importação

def dto(numero):
    return ImovelScraper(titulo=f"Imóvel {numero}", url=URL.format(numero), cidade="Campinas",
                         estado="SP", valor_avaliacao=200000.0, valor_leilao=100000.0,
                         modalidade="Leilão SFI - Edital Único", fonte="Caixa")


@pytest.fixture()
def importar(monkeypatch, sessao):
    def _importar(dtos, download, verificar_durante=None):
        class Baixador:
            UFS = cl.CaixaListaSegura.UFS

            def baixar_todos(self, *a, **k):
                if verificar_durante:
                    verificar_durante()
                if isinstance(download, Exception):
                    raise download
                return download

        class Scraper:
            def executar(self):
                return list(dtos)

        monkeypatch.setattr(scraper_service, "CaixaDownloader", Baixador)
        monkeypatch.setattr(scraper_service, "CaixaScraper", Scraper)
        monkeypatch.setattr(ScraperService, "preparar_fila_fotos_caixa", lambda self, i: {"pendentes": 0})
        return ScraperService(sessao).atualizar_lista_caixa()

    return _importar


def estado(sessao):
    sessao.expire_all()
    return sessao.get(CaixaDataWorkerState, 1)


def tudo_ok(geracao="2026-10-27"):
    return {"sucesso": list(cl.CaixaListaSegura.UFS), "falhas": [], "bloqueado": False,
            "geracoes": {uf: geracao for uf in cl.CaixaListaSegura.UFS}}


def test_marca_de_descarga_em_curso_gravada_antes_e_retirada_no_fim(importar, sessao):
    vistos = []

    def durante():
        assert not sessao.in_transaction()  # o commit da marca já aconteceu
        vistos.append(estado(sessao).bloqueado_ate)

    importar([dto(1)], tudo_ok(), verificar_durante=durante)

    assert vistos == [ce.PARAGEM_MANUAL]
    assert estado(sessao).bloqueado_ate is None


def test_bloqueio_na_descarga_para_todas_as_rotinas(importar, sessao):
    from app.services.caixa_rotinas import executar_lote_datas

    r = importar([dto(1)], {"sucesso": ["AC"], "falhas": [{"uf": "AL"}], "bloqueado": True,
                            "uf_bloqueada": "AL", "paragem": "REDIRECIONADO", "geracoes": {}})

    atual = estado(sessao)
    assert atual.bloqueado_ate == ce.PARAGEM_MANUAL and atual.bloqueios_consecutivos == 1
    assert r["imoveis_removidos"] == 0
    assert executar_lote_datas(sessao)["aguardando_bloqueio"] is True


def test_excecao_na_descarga_deixa_tudo_parado(importar, sessao):
    with pytest.raises(RuntimeError):
        importar([dto(1)], RuntimeError("o processo caiu"))
    assert estado(sessao).bloqueado_ate == ce.PARAGEM_MANUAL


def test_remocao_acima_do_limite_e_recusada(importar, sessao, fabrica):
    for n in range(100, 160):  # 60 imóveis que "desapareceriam" (> 50)
        fabrica.imovel(url=URL.format(n), fonte="Caixa")

    r = importar([dto(1)], tudo_ok())

    assert r["imoveis_removidos"] == 0 and r["remocao_recusada"] == 60
    assert sessao.query(Imovel).filter(Imovel.fonte == "Caixa").count() == 61


def test_remocao_dentro_do_limite_continua_a_funcionar(importar, sessao, fabrica):
    fabrica.imovel(url=URL.format(3), fonte="Caixa")
    r = importar([dto(1)], tudo_ok())
    assert r["imoveis_removidos"] == 1 and r["remocao_recusada"] == 0


def test_sem_remocoes_so_conta_os_ausentes(monkeypatch, sessao, fabrica):
    fabrica.imovel(url=URL.format(3), fonte="Caixa")
    fabrica.imovel(url=URL.format(4), fonte="Caixa")

    class Baixador:
        UFS = cl.CaixaListaSegura.UFS

        def baixar_todos(self, *a, **k):
            return tudo_ok()

    class Scraper:
        def executar(self):
            return [dto(1)]

    monkeypatch.setattr(scraper_service, "CaixaDownloader", Baixador)
    monkeypatch.setattr(scraper_service, "CaixaScraper", Scraper)
    monkeypatch.setattr(ScraperService, "preparar_fila_fotos_caixa", lambda self, i: {"pendentes": 0})

    r = ScraperService(sessao).atualizar_lista_caixa(remover=False)

    assert r["imoveis_removidos"] == 0 and r["ausentes_da_lista"] == 2
    assert sessao.query(Imovel).filter(Imovel.fonte == "Caixa").count() == 3


def test_ausentes_tambem_aparecem_quando_remove(importar, sessao, fabrica):
    fabrica.imovel(url=URL.format(3), fonte="Caixa")
    r = importar([dto(1)], tudo_ok())
    assert r["imoveis_removidos"] == 1 and r["ausentes_da_lista"] == 1


def test_listas_com_datas_de_geracao_diferentes_nao_removem(importar, sessao, fabrica):
    fabrica.imovel(url=URL.format(3), fonte="Caixa")
    download = tudo_ok()
    download["geracoes"]["SP"] = "2026-10-26"

    r = importar([dto(1)], download)

    assert r["imoveis_removidos"] == 0
    assert sessao.query(Imovel).filter(Imovel.url == URL.format(3)).count() == 1


def test_importacao_usa_o_downloader_seguro():
    assert scraper_service.CaixaDownloader is cl.CaixaListaSegura
