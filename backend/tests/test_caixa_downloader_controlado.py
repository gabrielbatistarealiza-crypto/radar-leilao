"""Listas com browser real (CaixaDownloaderControlado), sem rede e sem abrir o Chrome.

O browser e o download são trocados por falsos; verifica 1 tentativa por UF,
paragem na primeira falha de qualquer tipo, pausa entre UFs e datas de geração.
"""
from pathlib import Path

import pytest

from app.models.caixa_data_worker_state import CaixaDataWorkerState
from app.services import caixa_downloader as cd
from app.services import scraper_service
from app.services.caixa_datas_edital import PARAGEM_MANUAL
from app.services.scraper_service import ScraperService
from app.utils.browser import CaixaBloqueioError


def csv_caixa(uf, geracao="29/10/2026"):
    return (f" Lista de Imóveis da Caixa;;Data de geração:;{geracao};;;;;;;\n"
            " N° do imóvel;UF;Cidade;Bairro;Endereço;Preço;Valor de avaliação;Desconto;"
            "Financiamento;Descrição;Modalidade de venda;Link de acesso\n").encode("cp1252")


class DriverFalso:
    def __init__(self):
        self.fechado = False

    def quit(self):
        self.fechado = True


@pytest.fixture()
def baixador(tmp_path, monkeypatch):
    pausas, tentativas, drivers = [], [], []
    monkeypatch.setattr(cd.time, "sleep", pausas.append)

    def montar(respostas=None, falha_browser=False):
        respostas = respostas or {}
        b = cd.CaixaDownloaderControlado(intervalo=45, pasta_dados=tmp_path)

        def criar_driver():
            if falha_browser:
                raise RuntimeError("chrome ausente")
            b.driver = DriverFalso()
            drivers.append(b.driver)

        def baixar_estado(uf, tentativas=3):
            tentativas_usadas.append(tentativas)
            r = respostas.get(uf, "ok")
            if r == "captcha":
                raise CaixaBloqueioError("captcha")
            if r == "falha":
                return {"uf": uf, "sucesso": False, "erro": "Download não apareceu na pasta."}
            caminho = Path(tmp_path) / f"Lista_imoveis_{uf}.csv"
            caminho.write_bytes(b"<html>erro</html>" if r == "html" else csv_caixa(uf))
            return {"uf": uf, "sucesso": True, "arquivo": str(caminho)}

        tentativas_usadas = tentativas
        b.criar_driver = criar_driver
        b.baixar_estado = baixar_estado
        return b

    montar.pausas, montar.tentativas, montar.drivers = pausas, tentativas, drivers
    return montar


def test_descarrega_com_uma_tentativa_por_uf_e_pausa(baixador):
    r = baixador().baixar_todos(max_ufs=3)

    assert r["sucesso"] == ["AC", "AL", "AP"] and r["bloqueado"] is False and r["pedidos"] == 3
    assert set(r["geracoes"].values()) == {"2026-10-29"} and r["com_browser"] is True
    assert baixador.tentativas == [1, 1, 1]
    assert baixador.pausas == [45, 45]
    assert baixador.drivers[0].fechado is True


@pytest.mark.parametrize("resposta, motivo", [
    ("captcha", "CAPTCHA"), ("falha", "FALHA_DOWNLOAD"), ("html", "NAO_E_CSV_DA_CAIXA"),
])
def test_para_na_primeira_falha_de_qualquer_tipo(baixador, resposta, motivo):
    r = baixador({"AL": resposta}).baixar_todos(max_ufs=5)

    assert r["bloqueado"] is True and r["paragem"] == motivo and r["uf_bloqueada"] == "AL"
    assert r["sucesso"] == ["AC"] and r["pedidos"] == 2  # nada depois do AL
    assert baixador.tentativas == [1, 1]
    assert baixador.drivers[0].fechado is True


def test_browser_que_nao_arranca_para_sem_pedidos(baixador):
    r = baixador(falha_browser=True).baixar_todos()
    assert r["bloqueado"] is True and r["paragem"] == "FALHA_BROWSER" and r["pedidos"] == 0


def test_importacao_com_browser_usa_o_downloader_controlado_e_para(monkeypatch, sessao):
    usados = []

    class Controlado:
        def __init__(self):
            usados.append("browser")

        def baixar_todos(self, max_ufs=None):
            return {"sucesso": ["AC"], "falhas": [{"uf": "AL"}], "bloqueado": True,
                    "uf_bloqueada": "AL", "paragem": "CAPTCHA", "pedidos": 2, "geracoes": {}}

    class Scraper:
        def executar(self):
            return []

    monkeypatch.setattr(cd, "CaixaDownloaderControlado", Controlado)
    monkeypatch.setattr(scraper_service, "CaixaScraper", Scraper)
    monkeypatch.setattr(ScraperService, "preparar_fila_fotos_caixa", lambda self, i: {"pendentes": 0})

    r = ScraperService(sessao).atualizar_lista_caixa(max_ufs=5, remover=False, com_browser=True)

    sessao.expire_all()
    assert usados == ["browser"] and r["download"]["paragem"] == "CAPTCHA"
    assert sessao.get(CaixaDataWorkerState, 1).bloqueado_ate == PARAGEM_MANUAL


def test_sem_com_browser_continua_a_usar_requests():
    from app.services.caixa_lista_segura import CaixaListaSegura

    assert scraper_service.CaixaDownloader is CaixaListaSegura
