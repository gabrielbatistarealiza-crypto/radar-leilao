"""Porteiro comum de acesso à CAIXA (app/services/caixa_acesso.py).

Sem rede e sem navegador: Browser, downloader e serviços são trocados por
versões falsas. Base de dados: a de teste do conftest (SQLite em memória por
omissão). O teste do lock entre processos só corre com TEST_DATABASE_URL a
apontar para um PostgreSQL de teste.
"""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.models.caixa_data_worker_state import CaixaDataWorkerState
from app.models.imovel import Imovel, ImovelFotoVerificacao
from app.routers import imoveis as imoveis_router
from app.services import caixa_acesso, caixa_rotinas, scraper_service
from app.services.caixa_acesso import (
    CaixaEmEspera,
    CaixaOcupada,
    acesso_caixa,
    acesso_caixa_http,
    registrar_bloqueio_caixa,
)
from app.services.caixa_downloader import CaixaDownloader
from app.services.caixa_worker_lock import CAIXA_COLETA_LOCK
from app.services.scraper_service import ScraperService
from app.utils.browser import Browser, CaixaBloqueioError

URL = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"


@pytest.fixture(autouse=True)
def lock_livre():
    assert not CAIXA_COLETA_LOCK.locked(), "lock preso por um teste anterior"
    yield
    assert not CAIXA_COLETA_LOCK.locked(), "o porteiro não libertou o lock"


@pytest.fixture(autouse=True)
def sem_pausas(monkeypatch):
    pausas = []
    monkeypatch.setattr(scraper_service.time, "sleep", lambda s: pausas.append(s))
    monkeypatch.setattr(imoveis_router.time, "sleep", lambda s: pausas.append(s))
    return pausas


def gravar_espera(sessao, horas=5, bloqueios=1):
    ate = datetime.utcnow() + timedelta(hours=horas)
    sessao.add(
        CaixaDataWorkerState(
            id=1, ativo=True, bloqueado_ate=ate, bloqueios_consecutivos=bloqueios
        )
    )
    sessao.commit()
    return ate


def estado(sessao):
    sessao.expire_all()
    return sessao.get(CaixaDataWorkerState, 1)


def imovel_caixa(fabrica, numero, pendente_fotos=False):
    imovel = fabrica.imovel(fonte="Caixa", url=URL.format(numero))
    if pendente_fotos:
        fabrica.sessao.add(
            ImovelFotoVerificacao(imovel_id=imovel.id, resultado="PENDENTE")
        )
        fabrica.sessao.commit()
    return imovel


# ------------------------------------------------------------- porteiro

def test_deixa_passar_sem_estado(sessao):
    with acesso_caixa(sessao, "teste"):
        assert CAIXA_COLETA_LOCK.locked()


def test_recusa_durante_a_espera_e_liberta_o_lock(sessao):
    ate = gravar_espera(sessao)
    with pytest.raises(CaixaEmEspera) as erro:
        with acesso_caixa(sessao, "teste"):
            pytest.fail("não devia entrar")
    assert erro.value.bloqueado_ate == ate
    assert erro.value.segundos_restantes > 0


def test_deixa_passar_depois_da_espera(sessao):
    gravar_espera(sessao, horas=-1)
    with acesso_caixa(sessao, "teste"):
        pass


def test_le_a_espera_gravada_por_outra_sessao(sessao, motor):
    # A sessão do porteiro já tinha lido o estado antes da espera existir.
    sessao.add(CaixaDataWorkerState(id=1, ativo=True))
    sessao.commit()
    sessao.get(CaixaDataWorkerState, 1)

    outra = sessionmaker(bind=motor)()
    registrar_bloqueio_caixa(outra, "outro-caminho")
    outra.close()

    with pytest.raises(CaixaEmEspera):
        with acesso_caixa(sessao, "teste"):
            pass


def test_lock_ocupado_recusa_sem_esperar(sessao):
    CAIXA_COLETA_LOCK.acquire()
    try:
        with pytest.raises(CaixaOcupada):
            with acesso_caixa(sessao, "teste", esperar=False):
                pass
    finally:
        CAIXA_COLETA_LOCK.release()


def test_liberta_o_lock_quando_o_corpo_falha(sessao):
    with pytest.raises(RuntimeError):
        with acesso_caixa(sessao, "teste"):
            raise RuntimeError("falha a meio")


def test_http_responde_429_em_espera_e_409_ocupado(sessao):
    gravar_espera(sessao)
    with pytest.raises(HTTPException) as erro:
        with acesso_caixa_http(sessao, "teste"):
            pass
    assert erro.value.status_code == 429

    sessao.query(CaixaDataWorkerState).delete()
    sessao.commit()
    CAIXA_COLETA_LOCK.acquire()
    try:
        with pytest.raises(HTTPException) as erro:
            with acesso_caixa_http(sessao, "teste"):
                pass
        assert erro.value.status_code == 409
    finally:
        CAIXA_COLETA_LOCK.release()


# ----------------------------------------------------- registo do bloqueio

def test_registrar_sem_linha_de_estado_cria_e_grava(sessao, motor):
    agora = datetime(2026, 10, 23, 12, 0, 0)
    assert registrar_bloqueio_caixa(sessao, "teste", agora) == 12

    outra = sessionmaker(bind=motor)()
    gravado = outra.get(CaixaDataWorkerState, 1)
    assert gravado.bloqueios_consecutivos == 1
    assert gravado.bloqueado_ate == agora + timedelta(hours=12)
    outra.close()

    assert registrar_bloqueio_caixa(sessao, "teste", agora) == 24


def test_worker_de_fotos_sem_estado_grava_a_espera(sessao, monkeypatch):
    """Regressão do antigo `None += 1` em main.py."""
    monkeypatch.setattr(
        ScraperService,
        "processar_fila_fotos_caixa",
        lambda self, limite: {"processados": 1, "bloqueados": 1},
    )

    resultado = caixa_rotinas.executar_lote_fotos(sessao, 5)

    assert resultado["horas_espera"] == 12
    assert estado(sessao).bloqueios_consecutivos == 1
    assert estado(sessao).bloqueado_ate is not None


def test_worker_de_fotos_em_espera_nao_consulta(sessao, monkeypatch):
    gravar_espera(sessao)
    chamadas = []
    monkeypatch.setattr(
        ScraperService,
        "processar_fila_fotos_caixa",
        lambda self, limite: chamadas.append(limite),
    )

    resultado = caixa_rotinas.executar_lote_fotos(sessao, 5)

    assert resultado["aguardando_bloqueio"] is True
    assert chamadas == []


def test_worker_ocupado_nao_consulta(sessao, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        ScraperService,
        "processar_fila_fotos_caixa",
        lambda self, limite: chamadas.append(limite),
    )
    CAIXA_COLETA_LOCK.acquire()
    try:
        # Simula outra rotina com o lock: o worker tem de desistir, não esperar.
        monkeypatch.setattr(
            caixa_rotinas,
            "acesso_caixa",
            lambda db, origem: acesso_caixa(db, origem, esperar=False),
        )
        assert caixa_rotinas.executar_lote_fotos(sessao, 5) == {"ocupado": True}
    finally:
        CAIXA_COLETA_LOCK.release()
    assert chamadas == []


def test_espera_sobrevive_a_reinicio_tambem_nas_fotos(sessao, motor, monkeypatch):
    monkeypatch.setattr(
        ScraperService,
        "processar_fila_fotos_caixa",
        lambda self, limite: {"processados": 1, "bloqueados": 1},
    )
    caixa_rotinas.executar_lote_fotos(sessao, 5)

    # "Processo novo": outra sessão, nada em memória.
    nova = sessionmaker(bind=motor)()
    chamadas = []
    monkeypatch.setattr(
        ScraperService,
        "processar_fila_fotos_caixa",
        lambda self, limite: chamadas.append(limite),
    )
    assert caixa_rotinas.executar_lote_fotos(nova, 5)["aguardando_bloqueio"] is True
    assert caixa_rotinas.executar_lote_datas(nova)["aguardando_bloqueio"] is True
    assert chamadas == []
    nova.close()


# --------------------------------------------------------------- importação

class DownloaderContador:
    chamadas = 0
    UFS = list(CaixaDownloader.UFS)

    def __init__(self, resultado=None):
        self._resultado = resultado

    def baixar_todos(self, *args, **kwargs):
        DownloaderContador.chamadas += 1
        return {"sucesso": [], "falhas": [], "bloqueado": True, "uf_bloqueada": "AC"}


def test_importacao_em_espera_nao_chama_o_downloader(sessao, monkeypatch):
    gravar_espera(sessao)
    DownloaderContador.chamadas = 0
    monkeypatch.setattr(scraper_service, "CaixaDownloader", DownloaderContador)

    resultado = caixa_rotinas.executar_importacao(sessao)

    assert resultado["aguardando_bloqueio"] is True
    assert DownloaderContador.chamadas == 0


def test_importacao_manual_em_espera_responde_429(sessao, monkeypatch):
    from app.routers.scraper import atualizar_lista_caixa as endpoint

    gravar_espera(sessao)
    DownloaderContador.chamadas = 0
    monkeypatch.setattr(scraper_service, "CaixaDownloader", DownloaderContador)

    with pytest.raises(HTTPException) as erro:
        endpoint(db=sessao, administrador=None)
    assert erro.value.status_code == 429
    assert DownloaderContador.chamadas == 0


def test_download_bloqueado_grava_a_espera(sessao, monkeypatch):
    class ScraperVazio:
        def executar(self):
            return []

    DownloaderContador.chamadas = 0
    monkeypatch.setattr(scraper_service, "CaixaDownloader", DownloaderContador)
    monkeypatch.setattr(scraper_service, "CaixaScraper", ScraperVazio)
    monkeypatch.setattr(
        ScraperService, "preparar_fila_fotos_caixa", lambda self, imoveis: {"pendentes": 0}
    )

    caixa_rotinas.executar_importacao(sessao)

    assert DownloaderContador.chamadas == 1
    assert estado(sessao).bloqueado_ate is not None


# -------------------------------------------------------------- downloader

class DriverFalso:
    def __init__(self, html, titulo=""):
        self.page_source = html
        self.title = titulo
        self.gets = 0

    def get(self, url):
        self.gets += 1

    def quit(self):
        pass


PAGINA_CAPTCHA = (
    "<html><head><title>Radware Bot Manager CAPTCHA</title></head>"
    "<body>Precisamos fazer uma verificação de segurança</body></html>"
)
PAGINA_NORMAL_COM_SCRIPT = (
    "<html><head><script>var radware = 'captcha';</script></head>"
    "<body><select id='cmb_estado'></select></body></html>"
)


@pytest.fixture()
def downloader(tmp_path, monkeypatch):
    baixador = CaixaDownloader()
    # Nunca mexe nos CSVs reais de app/scrapers/dados.
    baixador.pasta_dados = tmp_path
    monkeypatch.setattr(baixador, "limpar_arquivos_estado", lambda uf: None)
    monkeypatch.setattr("app.services.caixa_downloader.time.sleep", lambda s: None)
    return baixador


def test_pagina_de_download_com_captcha_para_sem_repetir(downloader):
    downloader.driver = DriverFalso(PAGINA_CAPTCHA, "Radware Bot Manager CAPTCHA")
    with pytest.raises(CaixaBloqueioError):
        downloader.baixar_estado("AC", tentativas=3)
    assert downloader.driver.gets == 1


def test_script_do_radware_na_pagina_normal_nao_e_bloqueio(downloader):
    downloader.driver = DriverFalso(PAGINA_NORMAL_COM_SCRIPT)
    downloader._verificar_pagina_bloqueada()  # não levanta


def test_arquivo_baixado_com_captcha_e_bloqueio(downloader, tmp_path):
    captcha = tmp_path / "captcha.csv"
    captcha.write_text(PAGINA_CAPTCHA, encoding="utf-8")
    csv = tmp_path / "lista.csv"
    csv.write_text("Lista de Imóveis;UF;Cidade;Bairro\n", encoding="utf-8")
    assert downloader._arquivo_indica_bloqueio(captcha) is True
    assert downloader._arquivo_indica_bloqueio(csv) is False


def test_baixar_todos_para_na_primeira_uf_bloqueada(downloader, monkeypatch):
    tentadas = []

    def baixar_estado(uf, tentativas=3):
        tentadas.append(uf)
        raise CaixaBloqueioError("captcha")

    monkeypatch.setattr(downloader, "criar_driver", lambda: None)
    monkeypatch.setattr(downloader, "baixar_estado", baixar_estado)

    resultado = downloader.baixar_todos()

    assert tentadas == [CaixaDownloader.UFS[0]]
    assert resultado["bloqueado"] is True
    assert resultado["uf_bloqueada"] == CaixaDownloader.UFS[0]
    assert resultado["sucesso"] == []


# ------------------------------------------------------ serviço de fotos

class BrowserFalso:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.urls = []

    def iniciar(self):
        pass

    def fechar(self):
        pass

    def coletar_imagens_galeria_sessao(self, url):
        self.urls.append(url)
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta, len(resposta)

    def coletar_imagens_galeria(self, url):
        return self.coletar_imagens_galeria_sessao(url)


def test_fila_de_fotos_para_no_primeiro_bloqueio(sessao, fabrica, monkeypatch):
    for n in (1, 2, 3):
        imovel_caixa(fabrica, n, pendente_fotos=True)
    falso = BrowserFalso([CaixaBloqueioError("captcha"), [], []])
    monkeypatch.setattr(scraper_service, "Browser", lambda: falso)

    resultado = ScraperService(sessao).processar_fila_fotos_caixa(10)

    assert resultado["bloqueados"] == 1
    assert len(falso.urls) == 1


def test_fila_de_fotos_espaca_os_imoveis(sessao, fabrica, monkeypatch, sem_pausas):
    monkeypatch.setenv("RADAR_CAIXA_FOTOS_INTERVALO_SEGUNDOS", "45")
    for n in (1, 2, 3):
        imovel_caixa(fabrica, n, pendente_fotos=True)
    falso = BrowserFalso([[], [], []])
    monkeypatch.setattr(scraper_service, "Browser", lambda: falso)

    ScraperService(sessao).processar_fila_fotos_caixa(10)

    assert len(falso.urls) == 3
    assert sem_pausas == [45, 45]


@pytest.mark.parametrize(
    "valor, esperado",
    [(None, 30), ("60", 60), ("1", 5), ("lento", 30)],
)
def test_intervalo_entre_fotos(monkeypatch, valor, esperado):
    if valor is None:
        monkeypatch.delenv("RADAR_CAIXA_FOTOS_INTERVALO_SEGUNDOS", raising=False)
    else:
        monkeypatch.setenv("RADAR_CAIXA_FOTOS_INTERVALO_SEGUNDOS", valor)
    assert caixa_acesso.intervalo_entre_fotos() == esperado


# --------------------------------------------------- endpoints de fotos

@pytest.fixture()
def admin_http(http, admin, autenticar):
    cabecalho = autenticar(admin)

    def post(caminho, **params):
        return http.post(caminho, params=params, headers=cabecalho)

    return post


@pytest.fixture()
def browser_falso(monkeypatch):
    criados = []

    def _instalar(respostas):
        falso = BrowserFalso(respostas)

        def fabrica_browser():
            criados.append(falso)
            return falso

        monkeypatch.setattr(imoveis_router, "Browser", fabrica_browser)
        return falso

    _instalar.criados = criados
    return _instalar


ENDPOINTS_FOTOS = [
    ("/imoveis/manutencao/coletar-imagens-caixa-lote", {"limite": 3}),
    ("/imoveis/manutencao/coletar-imagens-caixa-playwright", {"imovel_id": 1}),
    ("/imoveis/manutencao/processar-fila-fotos-caixa", {"limite": 3}),
    ("/imoveis/manutencao/testar-galeria-caixa-playwright", {"limite": 3}),
]


@pytest.mark.parametrize("caminho, params", ENDPOINTS_FOTOS)
def test_endpoints_de_fotos_respeitam_a_espera(
    caminho, params, sessao, fabrica, admin_http, browser_falso
):
    imovel_caixa(fabrica, 1, pendente_fotos=True)
    gravar_espera(sessao)
    browser_falso([[]])

    resposta = admin_http(caminho, **params)

    assert resposta.status_code == 429
    assert browser_falso.criados == []


@pytest.mark.parametrize("caminho, params", ENDPOINTS_FOTOS)
def test_endpoints_de_fotos_recusam_com_outra_consulta_em_curso(
    caminho, params, fabrica, admin_http, browser_falso
):
    imovel_caixa(fabrica, 1, pendente_fotos=True)
    browser_falso([[]])
    CAIXA_COLETA_LOCK.acquire()
    try:
        resposta = admin_http(caminho, **params)
    finally:
        CAIXA_COLETA_LOCK.release()

    assert resposta.status_code == 409
    assert browser_falso.criados == []


@pytest.mark.parametrize("caminho, params", ENDPOINTS_FOTOS)
def test_sem_login_da_401_mesmo_em_espera_ou_com_lock_ocupado(
    caminho, params, sessao, fabrica, http, browser_falso
):
    """A autenticação corre antes do porteiro: não revela o estado do bloqueio."""
    imovel_caixa(fabrica, 1, pendente_fotos=True)
    browser_falso([[]])

    gravar_espera(sessao)
    assert http.post(caminho, params=params).status_code == 401

    sessao.query(CaixaDataWorkerState).delete()
    sessao.commit()
    CAIXA_COLETA_LOCK.acquire()
    try:
        assert http.post(caminho, params=params).status_code == 401
    finally:
        CAIXA_COLETA_LOCK.release()

    assert browser_falso.criados == []


@pytest.mark.parametrize("caminho, params", ENDPOINTS_FOTOS)
def test_sem_perfil_admin_da_403_antes_do_porteiro(
    caminho, params, sessao, fabrica, http, cliente, autenticar, browser_falso
):
    imovel_caixa(fabrica, 1, pendente_fotos=True)
    browser_falso([[]])
    gravar_espera(sessao)

    resposta = http.post(caminho, params=params, headers=autenticar(cliente))

    assert resposta.status_code == 403
    assert browser_falso.criados == []


@pytest.mark.parametrize("caminho, params", ENDPOINTS_FOTOS)
def test_pedido_sem_login_nao_adquire_o_lock(
    caminho, params, fabrica, http, monkeypatch, browser_falso
):
    imovel_caixa(fabrica, 1, pendente_fotos=True)
    browser_falso([[]])
    entradas = []
    original = imoveis_router.acesso_caixa_http

    def espiao(db, origem):
        entradas.append(origem)
        return original(db, origem)

    monkeypatch.setattr(imoveis_router, "acesso_caixa_http", espiao)

    assert http.post(caminho, params=params).status_code == 401
    assert entradas == []


def test_status_das_datas_devolve_o_intervalo_configurado(sessao, monkeypatch):
    from app.routers.scraper import status_worker_datas_caixa

    monkeypatch.setenv("RADAR_CAIXA_DATAS_INTERVALO_SEGUNDOS", "120")
    assert status_worker_datas_caixa(db=sessao, administrador=None)["intervalo_segundos"] == 120

    monkeypatch.delenv("RADAR_CAIXA_DATAS_INTERVALO_SEGUNDOS")
    from app.services.caixa_datas_worker import INTERVALO_PADRAO_SEGUNDOS

    status = status_worker_datas_caixa(db=sessao, administrador=None)
    assert status["intervalo_segundos"] == INTERVALO_PADRAO_SEGUNDOS
    assert status["pedidos_hoje"] == 0 and status["limite_diario_pedidos"] == 20


def test_lote_para_no_captcha_e_grava_a_espera(sessao, fabrica, admin_http, browser_falso):
    for n in (1, 2, 3):
        imovel_caixa(fabrica, n)
    falso = browser_falso([CaixaBloqueioError("captcha"), [], []])

    resposta = admin_http("/imoveis/manutencao/coletar-imagens-caixa-lote", limite=3)

    corpo = resposta.json()
    assert resposta.status_code == 200
    assert corpo["bloqueado"] is True
    assert corpo["processados"] == 0  # o offset não salta o imóvel bloqueado
    assert len(falso.urls) == 1
    assert estado(sessao).bloqueado_ate is not None


def test_teste_de_galeria_para_no_captcha(sessao, fabrica, admin_http, browser_falso):
    for n in (1, 2, 3):
        imovel_caixa(fabrica, n)
    falso = browser_falso([CaixaBloqueioError("captcha"), [], []])

    resposta = admin_http("/imoveis/manutencao/testar-galeria-caixa-playwright", limite=3)

    assert resposta.json()["bloqueado"] is True
    assert len(falso.urls) == 1
    assert estado(sessao).bloqueado_ate is not None


def test_coleta_de_um_imovel_com_captcha_responde_429(sessao, fabrica, admin_http, browser_falso):
    imovel = imovel_caixa(fabrica, 1)
    browser_falso([CaixaBloqueioError("captcha")])

    resposta = admin_http(
        "/imoveis/manutencao/coletar-imagens-caixa-playwright", imovel_id=imovel.id
    )

    assert resposta.status_code == 429
    assert estado(sessao).bloqueado_ate is not None


def test_fila_manual_com_bloqueio_grava_a_espera(sessao, admin_http, monkeypatch):
    monkeypatch.setattr(
        ScraperService,
        "processar_fila_fotos_caixa",
        lambda self, limite: {"processados": 1, "bloqueados": 1},
    )

    resposta = admin_http("/imoveis/manutencao/processar-fila-fotos-caixa", limite=3)

    assert resposta.json()["horas_espera"] == 12
    assert estado(sessao).bloqueado_ate is not None


# ------------------------------------------------------- código removido

def test_browser_ja_nao_pede_para_resolver_captcha_a_mao():
    assert not hasattr(Browser, "abrir")


# A recusa dos scripts legados está em tests/test_scripts_legados.py
# (verificação estática: os scripts não são executados).


# ---------------------------------------- lock entre processos (PostgreSQL)

def test_lock_consultivo_impede_dois_processos(motor):
    if motor.dialect.name != "postgresql":
        pytest.skip("só com TEST_DATABASE_URL a apontar para PostgreSQL de teste")
    fabrica = sessionmaker(bind=motor)
    a, b = fabrica(), fabrica()
    ligacao = caixa_acesso._adquirir_lock_entre_processos(a)
    try:
        with pytest.raises(CaixaOcupada):
            caixa_acesso._adquirir_lock_entre_processos(b)
    finally:
        caixa_acesso._libertar_lock_entre_processos(ligacao)
    segunda = caixa_acesso._adquirir_lock_entre_processos(b)
    caixa_acesso._libertar_lock_entre_processos(segunda)
    a.close()
    b.close()
