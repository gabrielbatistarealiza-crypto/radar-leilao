"""Download das listas da CAIXA perante CAPTCHA, HTML e falhas.

Sem rede e sem navegador: o driver é falso e a pasta de dados é temporária
(os CSVs reais em app/scrapers/dados nunca são tocados).
"""
import pytest

from app.models.caixa_data_worker_state import CaixaDataWorkerState
from app.scrapers.caixa import CaixaScraper
from app.services import caixa_rotinas, scraper_service
from app.services.caixa_downloader import CaixaDownloader, texto_indica_bloqueio
from app.services.scraper_service import ScraperService
from app.utils.browser import CaixaBloqueioError

CSV_VALIDO = (
    "Lista de Imóveis da Caixa\n"
    "N° do imóvel;UF;Cidade;Bairro;Endereço;Preço;Valor de avaliação;Desconto;"
    "Financiamento;Descrição;Modalidade de venda;Link de acesso\n"
    "1;SP;Campinas;Centro;Rua A;100.000,00;200.000,00;50;Sim;Casa;"
    "Leilão SFI - Edital Único;https://venda-imoveis.caixa.gov.br/x?hdnimovel=1\n"
) * 3
PAGINA_CAPTCHA = (
    "<html><head><title>Radware Bot Manager CAPTCHA</title></head>"
    "<body>Precisamos fazer uma verificação de segurança</body></html>"
)
PAGINA_ERRO_HTML = "<html><body><h1>Serviço indisponível</h1></body></html>"


class DriverFalso:
    def __init__(self, html, titulo=""):
        self.page_source = html
        self.title = titulo
        self.gets = 0

    def get(self, url):
        self.gets += 1

    def quit(self):
        pass


@pytest.fixture()
def baixador(tmp_path, monkeypatch):
    d = CaixaDownloader()
    d.pasta_dados = tmp_path
    monkeypatch.setattr("app.services.caixa_downloader.time.sleep", lambda s: None)
    return d


def escrever_csv_anterior(pasta, uf="AC", conteudo=CSV_VALIDO):
    caminho = pasta / f"Lista_imoveis_{uf}.csv"
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def ficheiros_topo(pasta):
    return sorted(p.name for p in pasta.iterdir() if p.is_file())


# ------------------------------------------------- deteção de bloqueio

@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Radware Bot Manager CAPTCHA", True),
        ("Estamos detectando comportamento malicioso no acesso", True),
        ("Precisamos fazer uma verificação de segurança", True),
        ("Access Denied", True),
        ("Request blocked", True),
        ("Lista de Imóveis da Caixa;UF;Cidade", False),
        ("", False),
    ],
)
def test_texto_indica_bloqueio(texto, esperado):
    assert texto_indica_bloqueio(texto) is esperado


def test_html_de_erro_nao_e_bloqueio_mas_nao_e_csv(baixador, tmp_path):
    pagina = tmp_path / "Lista_imoveis_AC.csv"
    pagina.write_text(PAGINA_ERRO_HTML, encoding="utf-8")
    assert baixador._arquivo_indica_bloqueio(pagina) is False
    assert baixador.validar_csv(pagina) is False


def test_csv_valido_e_aceite(baixador, tmp_path):
    caminho = escrever_csv_anterior(tmp_path)
    assert baixador.validar_csv(caminho) is True
    assert baixador._arquivo_indica_bloqueio(caminho) is False


# --------------------------------------------- reserva do CSV anterior

def test_captcha_na_pagina_preserva_o_csv_anterior(baixador, tmp_path):
    anterior = escrever_csv_anterior(tmp_path)
    baixador.driver = DriverFalso(PAGINA_CAPTCHA, "Radware Bot Manager CAPTCHA")

    with pytest.raises(CaixaBloqueioError):
        baixador.baixar_estado("AC", tentativas=3)

    assert baixador.driver.gets == 1  # sem novas tentativas
    assert anterior.read_text(encoding="utf-8") == CSV_VALIDO
    assert ficheiros_topo(tmp_path) == ["Lista_imoveis_AC.csv"]
    assert not (tmp_path / "_anterior").exists()


def test_ficheiro_de_captcha_baixado_e_descartado(baixador, tmp_path, monkeypatch):
    anterior = escrever_csv_anterior(tmp_path)

    def download_com_captcha(uf, tentativas=3):
        (tmp_path / f"Lista_imoveis_{uf}.csv").write_text(PAGINA_CAPTCHA, encoding="utf-8")
        raise CaixaBloqueioError("captcha no ficheiro")

    monkeypatch.setattr(baixador, "_baixar_estado_sem_reserva", download_com_captcha)

    with pytest.raises(CaixaBloqueioError):
        baixador.baixar_estado("AC")

    assert anterior.read_text(encoding="utf-8") == CSV_VALIDO
    assert ficheiros_topo(tmp_path) == ["Lista_imoveis_AC.csv"]


def test_falha_comum_repoe_o_csv_anterior(baixador, tmp_path, monkeypatch):
    anterior = escrever_csv_anterior(tmp_path)

    def download_falhado(uf, tentativas=3):
        (tmp_path / f"Lista_imoveis_{uf} (1).csv").write_text(PAGINA_ERRO_HTML, encoding="utf-8")
        return {"uf": uf, "sucesso": False, "erro": "não é CSV"}

    monkeypatch.setattr(baixador, "_baixar_estado_sem_reserva", download_falhado)

    assert baixador.baixar_estado("AC")["sucesso"] is False
    assert anterior.read_text(encoding="utf-8") == CSV_VALIDO
    assert ficheiros_topo(tmp_path) == ["Lista_imoveis_AC.csv"]


def test_sucesso_substitui_e_descarta_a_reserva(baixador, tmp_path, monkeypatch):
    escrever_csv_anterior(tmp_path, conteudo=CSV_VALIDO + "antigo\n")

    def download_ok(uf, tentativas=3):
        (tmp_path / f"Lista_imoveis_{uf}.csv").write_text(CSV_VALIDO, encoding="utf-8")
        return {"uf": uf, "sucesso": True}

    monkeypatch.setattr(baixador, "_baixar_estado_sem_reserva", download_ok)

    assert baixador.baixar_estado("AC")["sucesso"] is True
    assert (tmp_path / "Lista_imoveis_AC.csv").read_text(encoding="utf-8") == CSV_VALIDO
    assert not (tmp_path / "_anterior").exists()


def test_reserva_de_execucao_interrompida_e_reposta(baixador, tmp_path, monkeypatch):
    reserva = tmp_path / "_anterior" / "AC"
    reserva.mkdir(parents=True)
    (reserva / "Lista_imoveis_AC.csv").write_text(CSV_VALIDO, encoding="utf-8")

    monkeypatch.setattr(
        baixador,
        "_baixar_estado_sem_reserva",
        lambda uf, tentativas=3: {"uf": uf, "sucesso": False, "erro": "x"},
    )
    baixador.baixar_estado("AC")

    assert (tmp_path / "Lista_imoveis_AC.csv").read_text(encoding="utf-8") == CSV_VALIDO


def test_outras_ufs_nao_sao_tocadas(baixador, tmp_path, monkeypatch):
    escrever_csv_anterior(tmp_path, "AC")
    outra = escrever_csv_anterior(tmp_path, "AL")

    def download_com_captcha(uf, tentativas=3):
        raise CaixaBloqueioError("captcha")

    monkeypatch.setattr(baixador, "_baixar_estado_sem_reserva", download_com_captcha)
    with pytest.raises(CaixaBloqueioError):
        baixador.baixar_estado("AC")

    assert outra.read_text(encoding="utf-8") == CSV_VALIDO


def test_baixar_todos_para_e_preserva_todas_as_ufs(baixador, tmp_path, monkeypatch):
    for uf in CaixaDownloader.UFS:
        escrever_csv_anterior(tmp_path, uf)
    driver = DriverFalso(PAGINA_CAPTCHA, "Radware Bot Manager CAPTCHA")
    baixador.driver = driver
    monkeypatch.setattr(baixador, "criar_driver", lambda: None)

    resultado = baixador.baixar_todos()

    assert resultado["bloqueado"] is True
    assert resultado["uf_bloqueada"] == CaixaDownloader.UFS[0]
    assert driver.gets == 1  # uma só página aberta; nenhuma outra UF tentada
    assert baixador.driver is None  # o Chrome foi fechado
    assert len(ficheiros_topo(tmp_path)) == len(CaixaDownloader.UFS)


# ------------------------------------------- importação após bloqueio

def test_importacao_com_download_bloqueado_regista_espera_e_nao_le_o_captcha(
    sessao, tmp_path, monkeypatch
):
    """Do CAPTCHA à espera gravada, sem processar a página de bloqueio."""
    escrever_csv_anterior(tmp_path, "AC")
    lidos = []

    class DownloaderNaPastaTemporaria(CaixaDownloader):
        def __init__(self):
            super().__init__()
            self.pasta_dados = tmp_path

        def criar_driver(self):
            self.driver = DriverFalso(PAGINA_CAPTCHA, "Radware Bot Manager CAPTCHA")

    class ScraperQueRegistaOsFicheiros:
        def executar(self):
            lidos.extend(ficheiros_topo(tmp_path))
            return []

    monkeypatch.setattr("app.services.caixa_downloader.time.sleep", lambda s: None)
    monkeypatch.setattr(scraper_service, "CaixaDownloader", DownloaderNaPastaTemporaria)
    monkeypatch.setattr(scraper_service, "CaixaScraper", ScraperQueRegistaOsFicheiros)
    monkeypatch.setattr(
        ScraperService, "preparar_fila_fotos_caixa", lambda self, imoveis: {"pendentes": 0}
    )

    caixa_rotinas.executar_importacao(sessao)

    sessao.expire_all()
    estado = sessao.get(CaixaDataWorkerState, 1)
    assert estado.bloqueado_ate is not None
    assert estado.bloqueios_consecutivos == 1
    # Só o CSV anterior, válido, estava em dados/ quando o importador leu.
    assert lidos == ["Lista_imoveis_AC.csv"]


def test_importador_ignora_a_pasta_de_reserva(tmp_path, monkeypatch):
    """CaixaScraper só lê .csv no nível de topo de dados/."""
    import app.scrapers.caixa as modulo

    (tmp_path / "_anterior" / "AC").mkdir(parents=True)
    (tmp_path / "_anterior" / "AC" / "Lista_imoveis_AC.csv").write_text(
        CSV_VALIDO, encoding="utf-8"
    )
    lidos = []
    monkeypatch.setattr(
        CaixaScraper, "_processar_csv", lambda self, caminho: lidos.append(caminho) or []
    )
    monkeypatch.setattr(modulo.os.path, "dirname", lambda _: str(tmp_path.parent))
    monkeypatch.setattr(
        modulo.os.path,
        "join",
        lambda *partes: str(tmp_path) if partes[-1] == "dados" else "/".join(partes),
    )

    CaixaScraper().executar()

    assert lidos == []
