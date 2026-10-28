"""Recolha de datas dos leilões da Caixa.

Não abre navegador nem acede à rede: requests, Selenium e o scraper são
trocados por versões falsas. A base de dados é a de teste do conftest.
"""
from datetime import date, datetime, timedelta

import pytest
from bs4 import BeautifulSoup

from app.models.caixa_data_worker_state import CaixaDataWorkerState
from app.models.imovel import Imovel
from app.scrapers import caixa as caixa_mod
from app.scrapers.caixa import CaixaFalhaTecnicaError, CaixaScraper
from app.services import caixa_datas_worker as worker
from app.services import scraper_service
from app.services.caixa_downloader import CaixaDownloader
from app.services.scraper_service import ScraperService

URL = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"

PAGINA_COM_DATAS = """
<html><head><title>Detalhe do imóvel</title>
<script>var protecao = "Radware Bot Manager captcha";</script></head>
<body><h5>Apartamento - Campinas</h5>
<span>Data do 1º Leilão - 10/11/2026 - 10h00</span>
<span>Data do 2º Leilão - 24/11/2026 - 10h00</span>
</body></html>
"""
PAGINA_SO_PRIMEIRO = "<html><body><p>1º Leilão: 05/12/2026</p></body></html>"
PAGINA_SEM_DATAS = "<html><body><p>Imóvel sem informação de leilão.</p></body></html>"
PAGINA_RADWARE_PT = (
    "<html><body><p>Estamos detectando comportamento malicioso no acesso.</p>"
    "</body></html>"
)
PAGINA_CAPTCHA = "<html><body><div>Resolva o CAPTCHA para continuar</div></body></html>"


def sopa(html):
    return BeautifulSoup(html, "html.parser")


@pytest.fixture(autouse=True)
def limpar_estado_global():
    CaixaScraper._bloqueio_ate = 0.0
    yield
    CaixaScraper._bloqueio_ate = 0.0


# ----------------------------------------------------- leitura da página

def test_extrai_as_duas_datas():
    assert CaixaScraper._extrair_datas_da_pagina(sopa(PAGINA_COM_DATAS)) == (
        date(2026, 11, 10),
        date(2026, 11, 24),
        None,
    )


def test_extrai_so_o_primeiro_leilao():
    assert CaixaScraper._extrair_datas_da_pagina(sopa(PAGINA_SO_PRIMEIRO)) == (
        date(2026, 12, 5),
        None,
        None,
    )


def test_data_impossivel_nao_apaga_a_outra_nem_levanta_erro():
    html = "<p>Data do 1º Leilão - 31/02/2026 Data do 2º Leilão - 10/03/2026</p>"
    assert CaixaScraper._extrair_datas_da_pagina(sopa(html)) == (
        None,
        date(2026, 3, 10),
        None,
    )


def test_data_impossivel_usa_a_ocorrencia_valida_seguinte():
    html = (
        "<p>1º Leilão: 99/99/2026</p>"
        "<p>Data do 1º Leilão - 05/12/2026</p>"
        "<p>Data do 2º Leilão - 19/12/2026</p>"
    )
    assert CaixaScraper._extrair_datas_da_pagina(sopa(html)) == (
        date(2026, 12, 5),
        date(2026, 12, 19),
        None,
    )


def test_pagina_sem_datas_devolve_vazio():
    assert CaixaScraper._extrair_datas_da_pagina(sopa(PAGINA_SEM_DATAS)) == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize("html", [PAGINA_RADWARE_PT, PAGINA_CAPTCHA])
def test_reconhece_paginas_de_bloqueio(html):
    texto = CaixaScraper._texto_visivel(sopa(html))
    assert CaixaScraper._pagina_bloqueada(texto)


def test_script_do_radware_na_pagina_normal_nao_e_bloqueio():
    texto = CaixaScraper._texto_visivel(sopa(PAGINA_COM_DATAS))
    assert "Radware" not in texto
    assert not CaixaScraper._pagina_bloqueada(texto)


def test_texto_vazio_e_bloqueio_no_selenium():
    assert CaixaScraper._pagina_bloqueada("")
    assert CaixaScraper._pagina_bloqueada("   ")


# ------------------------------------------------ extrair_datas_leilao

class RespostaFalsa:
    def __init__(self, html):
        self.text = html

    def raise_for_status(self):
        pass


@pytest.fixture()
def rede(monkeypatch):
    """Troca requests.get e o Selenium do scraper por respostas prontas."""

    def _rede(html=None, erro_requests=None, selenium=None, erro_selenium=None):
        chamadas = {"selenium": 0}

        def get_falso(*args, **kwargs):
            if erro_requests:
                raise erro_requests
            return RespostaFalsa(html)

        def selenium_falso(self, url):
            chamadas["selenium"] += 1
            if erro_selenium:
                raise erro_selenium
            return selenium

        monkeypatch.setattr(caixa_mod.requests, "get", get_falso)
        monkeypatch.setattr(
            CaixaScraper, "_coletar_detalhes_com_selenium", selenium_falso
        )
        return chamadas

    return _rede


def detalhes(primeiro=None, segundo=None, falha_tecnica=False):
    return {
        "imagens": [],
        "data_primeiro_leilao": primeiro,
        "data_segundo_leilao": segundo,
        "data_licitacao_aberta": None,
        "falha_tecnica": falha_tecnica,
    }


PAGINA_LICITACAO_ABERTA = (
    "<html><body><p>Data da Licitação Aberta - 15/12/2026</p></body></html>"
)


def test_requests_com_primeiro_e_segundo_leilao_nao_abre_o_selenium(rede):
    chamadas = rede(html=PAGINA_COM_DATAS, selenium=detalhes())
    scraper = CaixaScraper()
    datas = scraper.extrair_datas_leilao(URL.format(1))
    assert datas == (date(2026, 11, 10), date(2026, 11, 24), None)
    assert chamadas["selenium"] == 0
    assert not scraper.bloqueado


def test_requests_com_licitacao_aberta_nao_abre_o_selenium(rede):
    chamadas = rede(html=PAGINA_LICITACAO_ABERTA, selenium=detalhes())
    datas = CaixaScraper().extrair_datas_leilao(URL.format(1))
    assert datas == (None, None, date(2026, 12, 15))
    assert chamadas["selenium"] == 0


def test_requests_so_com_primeiro_leilao_ainda_abre_o_selenium(rede):
    chamadas = rede(
        html=PAGINA_SO_PRIMEIRO,
        selenium=detalhes(segundo=date(2026, 12, 19)),
    )
    datas = CaixaScraper().extrair_datas_leilao(URL.format(1))
    assert datas == (date(2026, 12, 5), date(2026, 12, 19), None)
    assert chamadas["selenium"] == 1


def test_requests_sem_datas_ainda_abre_o_selenium(rede):
    chamadas = rede(
        html=PAGINA_SEM_DATAS,
        selenium=detalhes(primeiro=date(2026, 11, 1), segundo=date(2026, 11, 8)),
    )
    datas = CaixaScraper().extrair_datas_leilao(URL.format(1))
    assert datas == (date(2026, 11, 1), date(2026, 11, 8), None)
    assert chamadas["selenium"] == 1


def test_captcha_no_requests_marca_bloqueio(rede):
    chamadas = rede(html=PAGINA_CAPTCHA, selenium=detalhes())
    scraper = CaixaScraper()
    assert scraper.extrair_datas_leilao(URL.format(1)) == (None, None, None)
    assert scraper.bloqueado
    assert chamadas["selenium"] == 0


def test_mensagem_radware_em_portugues_marca_bloqueio(rede):
    rede(html=PAGINA_RADWARE_PT, selenium=detalhes())
    scraper = CaixaScraper()
    scraper.extrair_datas_leilao(URL.format(1))
    assert scraper.bloqueado


def test_selenium_que_falha_sem_datas_e_falha_tecnica(rede):
    rede(erro_requests=TimeoutError("lento"), selenium=detalhes(falha_tecnica=True))
    with pytest.raises(CaixaFalhaTecnicaError):
        CaixaScraper().extrair_datas_leilao(URL.format(1))


def test_selenium_que_rebenta_sem_datas_e_falha_tecnica(rede):
    rede(html=PAGINA_SEM_DATAS, erro_selenium=RuntimeError("chrome ausente"))
    with pytest.raises(CaixaFalhaTecnicaError):
        CaixaScraper().extrair_datas_leilao(URL.format(1))


def test_selenium_que_falha_com_datas_parciais_devolve_as_parciais(rede):
    rede(html=PAGINA_SO_PRIMEIRO, selenium=detalhes(falha_tecnica=True))
    assert CaixaScraper().extrair_datas_leilao(URL.format(1)) == (
        date(2026, 12, 5),
        None,
        None,
    )


def test_data_impossivel_no_requests_vai_ao_selenium_sem_falha_tecnica(rede):
    chamadas = rede(
        html="<p>Data do 1º Leilão - 31/02/2026 Data do 2º Leilão - 10/03/2026</p>",
        selenium=detalhes(),
    )
    datas = CaixaScraper().extrair_datas_leilao(URL.format(1))
    assert datas == (None, date(2026, 3, 10), None)
    assert chamadas["selenium"] == 1


def test_pagina_lida_sem_datas_nao_e_falha_tecnica(rede):
    rede(html=PAGINA_SEM_DATAS, selenium=detalhes())
    assert CaixaScraper().extrair_datas_leilao(URL.format(1)) == (None, None, None)


# ---------------------------------------------- enriquecer_datas_caixa

def imovel_caixa(fabrica, numero, **campos):
    base = dict(
        fonte="Caixa",
        url=URL.format(numero),
        data_primeiro_leilao=None,
        data_segundo_leilao=None,
    )
    base.update(campos)
    return fabrica.imovel(**base)


@pytest.fixture()
def scraper_falso(monkeypatch):
    """Troca o CaixaScraper do serviço; cada URL devolve o que for pedido."""

    def _scraper(respostas):
        class ScraperFalso:
            def __init__(self):
                self.bloqueado = False
                self.driver = None

            def extrair_datas_leilao(self, url):
                resposta = respostas[url]
                if resposta == "BLOQUEIO":
                    self.bloqueado = True
                    return None, None, None
                if isinstance(resposta, Exception):
                    raise resposta
                return resposta

        monkeypatch.setattr(scraper_service, "CaixaScraper", ScraperFalso)

    return _scraper


def test_preenche_datas_em_falta_sem_apagar_as_existentes(sessao, fabrica, scraper_falso):
    existente = date(2026, 1, 1)
    imovel = imovel_caixa(fabrica, 1, data_primeiro_leilao=existente)
    scraper_falso({imovel.url: (date(2026, 9, 9), date(2026, 9, 20), None)})

    resultado = ScraperService(sessao).enriquecer_datas_caixa(limite=1)

    sessao.refresh(imovel)
    assert resultado["atualizados"] == 1
    assert imovel.data_primeiro_leilao == existente
    assert imovel.data_segundo_leilao == date(2026, 9, 20)


def test_pagina_sem_datas_nao_apaga_nada(sessao, fabrica, scraper_falso):
    existente = date(2026, 2, 2)
    imovel = imovel_caixa(fabrica, 1, data_primeiro_leilao=existente)
    scraper_falso({imovel.url: (None, None, None)})

    resultado = ScraperService(sessao).enriquecer_datas_caixa(limite=1)

    sessao.refresh(imovel)
    assert resultado["sem_dados_novos"] == 1
    assert imovel.data_primeiro_leilao == existente


def test_falha_tecnica_para_a_leva_e_nao_salta_os_seguintes(sessao, fabrica, scraper_falso):
    a = imovel_caixa(fabrica, 1)
    b = imovel_caixa(fabrica, 2)
    c = imovel_caixa(fabrica, 3)
    scraper_falso(
        {
            a.url: (date(2026, 9, 9), date(2026, 9, 20), None),
            b.url: CaixaFalhaTecnicaError("chrome"),
            c.url: (date(2026, 10, 1), date(2026, 10, 15), None),
        }
    )

    resultado = ScraperService(sessao).enriquecer_datas_caixa(limite=3)

    assert resultado["falha_tecnica"] is True
    assert resultado["falha_tecnica_id"] == b.id
    assert resultado["processados"] == 2
    assert resultado["atualizados"] == 1
    # O terceiro não foi consultado e continua na fila.
    assert resultado["tem_mais"] is True
    assert resultado["proximo_depois_id"] == b.id
    sessao.refresh(c)
    assert c.data_primeiro_leilao is None


# ------------------------------------------------------------- worker
# O comportamento do worker (imóvel + edital, paragem manual, sem Selenium)
# está em test_caixa_datas_edital.py.

def estado(sessao):
    sessao.expire_all()
    return sessao.get(CaixaDataWorkerState, 1)


def test_fila_concluida_nao_corre_ate_ser_reativada(sessao, fabrica):
    from app.services.caixa_datas_edital import RespostaCaixa

    a = imovel_caixa(fabrica, 1)
    pedidos = []

    def pedir(url, tipo):
        pedidos.append(url)
        return RespostaCaixa("OK", status=200, corpo=PAGINA_SEM_DATAS.encode())

    primeiro = worker.processar_lote_datas_caixa(sessao, pedir=pedir)
    assert primeiro["processados"] == 1 and primeiro["tem_mais"] is False
    assert worker.processar_lote_datas_caixa(sessao, pedir=pedir)["concluido"] is True
    assert worker.processar_lote_datas_caixa(sessao, pedir=pedir) == {"concluido": True, "pedidos": 0}
    assert pedidos == [a.url]

    worker.reativar_worker_datas_caixa(sessao)
    sessao.commit()

    resultado = worker.processar_lote_datas_caixa(sessao, pedir=pedir)
    assert resultado["processados"] == 1


def test_reativar_respeita_bloqueio_em_vigor(sessao):
    ate = datetime.utcnow() + timedelta(hours=5)
    sessao.add(CaixaDataWorkerState(id=1, ativo=False, cursor_id=40, bloqueado_ate=ate))
    sessao.commit()

    worker.reativar_worker_datas_caixa(sessao)
    sessao.commit()

    atual = estado(sessao)
    assert atual.ativo is True
    assert atual.cursor_id is None
    assert atual.bloqueado_ate == ate


def test_atualizar_lista_caixa_reativa_a_fila_de_datas(monkeypatch, sessao):
    sessao.add(CaixaDataWorkerState(id=1, ativo=False, cursor_id=99))
    sessao.commit()

    class DownloaderFalso:
        UFS = list(CaixaDownloader.UFS)

        def baixar_todos(self, *args, **kwargs):
            return {"sucesso": list(CaixaDownloader.UFS), "falhas": []}

    class ScraperFalso:
        def executar(self):
            return []

    monkeypatch.setattr(scraper_service, "CaixaDownloader", DownloaderFalso)
    monkeypatch.setattr(scraper_service, "CaixaScraper", ScraperFalso)
    monkeypatch.setattr(
        ScraperService, "preparar_fila_fotos_caixa", lambda self, imoveis: {"pendentes": 0}
    )

    ScraperService(sessao).atualizar_lista_caixa()

    atual = estado(sessao)
    assert atual.ativo is True
    assert atual.cursor_id is None


def test_atualizacao_que_falha_nao_reativa_a_fila(monkeypatch, sessao):
    sessao.add(CaixaDataWorkerState(id=1, ativo=False, cursor_id=99))
    sessao.commit()

    class DownloaderFalso:
        UFS = list(CaixaDownloader.UFS)

        def baixar_todos(self, *args, **kwargs):
            raise RuntimeError("sem rede")

    monkeypatch.setattr(scraper_service, "CaixaDownloader", DownloaderFalso)

    with pytest.raises(RuntimeError):
        ScraperService(sessao).atualizar_lista_caixa()

    atual = estado(sessao)
    assert atual.ativo is False
    assert atual.cursor_id == 99


# ------------------------------------------------- endpoint manual

def chamar_endpoint_manual(sessao, limite=1, depois_id=None):
    from app.routers.scraper import enriquecer_datas_caixa as endpoint

    return endpoint(
        limite=limite,
        depois_id=depois_id,
        db=sessao,
        administrador=None,
    )


@pytest.fixture()
def caixa_falsa(monkeypatch):
    """Troca o pedido HTTP do passo novo (só requests) por respostas prontas."""
    from app.services import caixa_datas_edital as ce

    def _caixa(respostas):
        pedidos = []

        def pedir(url, tipo):
            pedidos.append(url)
            r = respostas[url]
            return r if isinstance(r, ce.RespostaCaixa) else ce.RespostaCaixa("OK", status=200, corpo=r)

        monkeypatch.setattr(ce, "pedir_caixa", pedir)
        monkeypatch.setattr(
            CaixaScraper, "_coletar_detalhes_com_selenium",
            lambda *a, **k: pytest.fail("o endpoint manual não pode abrir o Selenium"),
        )
        return pedidos

    return _caixa


def test_endpoint_manual_para_ate_revisao_apos_bloqueio(sessao, fabrica, caixa_falsa):
    from app.services.caixa_datas_edital import PARAGEM_MANUAL, RespostaCaixa

    a = imovel_caixa(fabrica, 1)
    caixa_falsa({a.url: RespostaCaixa("REDIRECIONADO", status=302)})

    resultado = chamar_endpoint_manual(sessao)

    atual = estado(sessao)
    assert resultado["bloqueado"] is True and resultado["paragem"] == "REDIRECIONADO"
    assert resultado["resultados"] == [{"id": a.id, "status": "BLOQUEADO_CAIXA"}]
    assert atual.bloqueado_ate == PARAGEM_MANUAL and atual.bloqueios_consecutivos == 1
    # O endpoint manual não mexe no cursor do worker.
    assert atual.cursor_id is None


def test_endpoint_manual_recusa_enquanto_dura_a_paragem(sessao, fabrica, caixa_falsa):
    from fastapi import HTTPException

    from app.services.caixa_datas_edital import RespostaCaixa

    a = imovel_caixa(fabrica, 1)
    pedidos = caixa_falsa({a.url: RespostaCaixa("BLOQUEADO_HTTP_403", status=403)})
    chamar_endpoint_manual(sessao)

    with pytest.raises(HTTPException) as erro:
        chamar_endpoint_manual(sessao)
    assert erro.value.status_code == 429
    assert pedidos == [a.url]


def test_endpoint_manual_sem_bloqueio_devolve_o_formato_antigo(sessao, fabrica, caixa_falsa):
    a = imovel_caixa(fabrica, 1)
    b = imovel_caixa(fabrica, 2)
    caixa_falsa({a.url: PAGINA_COM_DATAS.encode()})

    resultado = chamar_endpoint_manual(sessao)

    assert resultado["processados"] == 1 and resultado["atualizados"] == 1
    assert resultado["tem_mais"] is True and resultado["proximo_depois_id"] == a.id
    assert resultado["resultados"] == [{"id": a.id, "status": "ATUALIZADO"}]
    sessao.refresh(a)
    assert a.data_primeiro_leilao == date(2026, 11, 10)
    atual = estado(sessao)
    assert atual.bloqueado_ate is None and atual.cursor_id is None


def test_endpoint_manual_respeita_o_limite_diario(sessao, fabrica, caixa_falsa, monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setenv("RADAR_CAIXA_DATAS_MAX_PEDIDOS_DIA", "1")
    a = imovel_caixa(fabrica, 1)
    b = imovel_caixa(fabrica, 2)
    pedidos = caixa_falsa({a.url: PAGINA_SEM_DATAS.encode(), b.url: PAGINA_SEM_DATAS.encode()})
    chamar_endpoint_manual(sessao)

    with pytest.raises(HTTPException) as erro:
        chamar_endpoint_manual(sessao, depois_id=a.id)
    assert erro.value.status_code == 429 and "Limite diário" in erro.value.detail
    assert pedidos == [a.url]


def test_espera_progressiva_partilhada_com_o_worker(sessao):
    atual = CaixaDataWorkerState(id=1, ativo=True, bloqueios_consecutivos=0)
    agora = datetime(2026, 10, 23, 12, 0, 0)
    horas = [worker.registrar_bloqueio(atual, agora) for _ in range(5)]
    assert horas == [12, 24, 48, 72, 72]


# -------------------------------------------------- ritmo do worker

@pytest.mark.parametrize(
    "valor, esperado",
    [
        (None, worker.INTERVALO_PADRAO_SEGUNDOS),
        ("", worker.INTERVALO_PADRAO_SEGUNDOS),
        ("120", 120),
        ("90.5", 90),
        ("3", worker.INTERVALO_MINIMO_SEGUNDOS),
        ("-5", worker.INTERVALO_MINIMO_SEGUNDOS),
        ("depressa", worker.INTERVALO_PADRAO_SEGUNDOS),
    ],
)
def test_intervalo_entre_imoveis(monkeypatch, valor, esperado):
    if valor is None:
        monkeypatch.delenv("RADAR_CAIXA_DATAS_INTERVALO_SEGUNDOS", raising=False)
    else:
        monkeypatch.setenv("RADAR_CAIXA_DATAS_INTERVALO_SEGUNDOS", valor)
    assert worker.intervalo_entre_imoveis() == esperado


def test_imoveis_com_ambas_as_datas_nao_entram_na_fila(sessao, fabrica, scraper_falso):
    imovel_caixa(
        fabrica,
        1,
        data_primeiro_leilao=date(2026, 9, 9),
        data_segundo_leilao=date(2026, 9, 20),
    )
    scraper_falso({})

    resultado = ScraperService(sessao).enriquecer_datas_caixa(limite=5)
    assert resultado["processados"] == 0
    assert sessao.query(Imovel).count() == 1
