import time
import os
import requests
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC



class CaixaDownloader:
    """
    Baixa automaticamente as listas de imóveis da CAIXA usando Selenium.

    Os arquivos sÃƒÂ£o salvos em:
    backend/app/scrapers/dados/
    """

    UFS = [
        "AC", "AL", "AP", "AM", "BA", "CE", "DF",
        "ES", "GO", "MA", "MT", "MS", "MG", "PA",
        "PB", "PR", "PE", "PI", "RJ", "RN", "RS",
        "RO", "RR", "SC", "SP", "SE", "TO",
    ]

    URL = "https://venda-imoveis.caixa.gov.br/sistema/download-lista.asp"

    def __init__(self):
        # services -> app -> scrapers -> dados
        self.pasta_dados = (
            Path(__file__).resolve().parent.parent
            / "scrapers"
            / "dados"
        )

        self.pasta_dados.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.driver = None

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
            )
        })


    # ============================================================
    # CRIA SELENIUM
    # ============================================================

    def criar_driver(self):
        """
        Cria o Chrome configurado para baixar os arquivos
        diretamente na pasta de dados.
        """

        options = webdriver.ChromeOptions()

        # Pasta onde o Chrome vai salvar os downloads
        prefs = {
            "download.default_directory": str(
                self.pasta_dados.resolve()
            ),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        }

        options.add_experimental_option(
            "prefs",
            prefs,
        )

        if os.getenv("BROWSER_HEADLESS", "false").lower() in {"1", "true", "yes"}:
            options.add_argument("--headless=new")
        options.add_argument("--start-maximized")

        self.driver = webdriver.Chrome(
            options=options,
        )

        self.driver.set_page_load_timeout(60)

        return self.driver

    # ============================================================
    # LIMPA ARQUIVOS ANTIGOS
    # ============================================================

    def limpar_arquivos_estado(self, uf):
        """
        Remove arquivos antigos daquele estado antes de iniciar
        um novo download.

        Isso evita:
        Lista_imoveis_SP (1).csv
        Lista_imoveis_SP (2).csv
        etc.
        """

        padrao = f"Lista_imoveis_{uf}*"

        for arquivo in self.pasta_dados.glob(padrao):
            try:
                if arquivo.is_file():
                    arquivo.unlink()
                    print(
                        f"[CAIXA] Removido arquivo antigo: "
                        f"{arquivo.name}"
                    )
            except OSError as erro:
                print(
                    f"[CAIXA] NÃƒÂ£o foi possÃƒÂ­vel remover "
                    f"{arquivo.name}: {erro}"
                )

    # ============================================================
    # VALIDA CSV
    # ============================================================

    def validar_csv(self, arquivo):
        """
        Confirma que o arquivo baixado realmente ÃƒÂ© uma lista
        de imóveis da CAIXA e nÃƒÂ£o uma pÃƒÂ¡gina HTML/CAPTCHA.
        """

        if not arquivo.exists():
            return False

        # Arquivos extremamente pequenos provavelmente sÃƒÂ£o erro.
        # NÃƒÂ£o exigimos mais 50 KB, pois alguns estados podem ter
        # poucos imóveis.
        tamanho = arquivo.stat().st_size

        if tamanho < 500:
            return False

        try:
            with open(arquivo, "rb") as f:
                conteudo = f.read(10000)

            # Tenta UTF-8 primeiro.
            try:
                inicio = conteudo.decode(
                    "utf-8-sig"
                ).lower()

            except UnicodeDecodeError:
                # Fallback para arquivos da CAIXA em Windows-1252.
                inicio = conteudo.decode(
                    "cp1252",
                    errors="ignore"
                ).lower()

        except Exception:
            return False

        # ============================================================
        # BLOQUEIO / CAPTCHA / HTML
        # ============================================================

        marcadores_bloqueio = [
            "<html",
            "<!doctype",
            "<head",
            "radware",
            "radware bot manager",
            "captcha",
            "access denied",
            "request blocked",
        ]

        for marcador in marcadores_bloqueio:
            if marcador in inicio:
                return False

        # ============================================================
        # CSV DA CAIXA
        # ============================================================

        # Usamos palavras sem depender de acentos.
        indicadores_csv = [
            "lista de im",
            "uf",
            "cidade",
            "bairro",
            "endere",
            "pre",
            "valor de avalia",
            "modalidade de venda",
            "link de acesso",
        ]

        encontrados = sum(
            1
            for indicador in indicadores_csv
            if indicador in inicio
        )

        return encontrados >= 4

    # ============================================================
    # ESPERA DOWNLOAD
    # ============================================================

    def esperar_download(
        self,
        uf,
        timeout=120,
    ):
        """
        Espera o Chrome terminar o download do arquivo.

        Retorna o caminho do arquivo baixado.
        """

        inicio = time.time()

        while time.time() - inicio < timeout:

            # Arquivos temporÃƒÂ¡rios do Chrome
            temporarios = list(
                self.pasta_dados.glob("*.crdownload")
            )

            # Procuramos arquivos relacionados ao estado
            arquivos = [
                arquivo
                for arquivo in self.pasta_dados.iterdir()
                if arquivo.is_file()
                and arquivo.name.startswith(
                    f"Lista_imoveis_{uf}"
                )
                and not arquivo.name.endswith(
                    ".crdownload"
                )
            ]

            # Se existe arquivo e nenhum download estÃƒÂ¡ em andamento
            if arquivos and not temporarios:

                # Pega o mais recente
                arquivos.sort(
                    key=lambda x: x.stat().st_mtime,
                    reverse=True,
                )

                arquivo = arquivos[0]

                # DÃƒÂ¡ um pequeno tempo para garantir que
                # o arquivo terminou de ser escrito.
                time.sleep(1)

                if arquivo.exists():
                    return arquivo

            time.sleep(1)

        return None

    # ============================================================
    # RENOMEIA DOWNLOAD
    # ============================================================

    def renomear_arquivo(self, arquivo, uf):
        """
        Padroniza o nome:

        Lista_imoveis_SP.csv

        independentemente de o Chrome ter criado:
        Lista_imoveis_SP (1).csv
        """

        destino = (
            self.pasta_dados
            / f"Lista_imoveis_{uf}.csv"
        )

        # Se for exatamente o destino
        if arquivo.resolve() == destino.resolve():
            return destino

        # Remove destino antigo se existir
        if destino.exists():
            destino.unlink()

        arquivo.rename(destino)

        return destino

    # ============================================================
    # BAIXA UM ESTADO
    # ============================================================

    def baixar_estado(
        self,
        uf,
        tentativas=3,
    ):
        """
        Seleciona um estado na pÃƒÂ¡gina da CAIXA e baixa o CSV.
        """

        uf = uf.upper().strip()

        if uf not in self.UFS:
            return {
                "uf": uf,
                "sucesso": False,
                "erro": "UF invÃƒÂ¡lida.",
            }

        ultimo_erro = None

        for tentativa in range(
            1,
            tentativas + 1,
        ):

            try:
                print()
                print(
                    f"[CAIXA] Baixando {uf} "
                    f"(tentativa {tentativa}/{tentativas})..."
                )

                # Remove possÃƒÂ­veis arquivos antigos
                self.limpar_arquivos_estado(uf)

                # Abre a pÃƒÂ¡gina novamente para cada estado.
                #
                # Isso deixa o processo muito mais previsÃƒÂ­vel
                # do que tentar reutilizar a pÃƒÂ¡gina anterior.
                self.driver.get(self.URL)

                wait = WebDriverWait(
                    self.driver,
                    30,
                )

                # ------------------------------------------------
                # SELECT DO ESTADO
                # ------------------------------------------------

                select_element = wait.until(
                    EC.presence_of_element_located(
                        (By.ID, "cmb_estado")
                    )
                )

                select = Select(select_element)

                # Confirma que a UF existe no select
                valores = [
                    opcao.get_attribute("value")
                    for opcao in select.options
                ]

                textos = [
                    opcao.text.strip().upper()
                    for opcao in select.options
                ]

                if uf not in valores and uf not in textos:
                    raise RuntimeError(
                        f"UF {uf} nÃƒÂ£o encontrada no select."
                    )

                # Primeiro tenta pelo value
                selecionado = False

                try:
                    select.select_by_value(uf)
                    selecionado = True
                except Exception:
                    pass

                # Se nÃƒÂ£o funcionar, tenta pelo texto
                if not selecionado:
                    select.select_by_visible_text(uf)

                print(
                    f"[CAIXA] {uf} selecionado."
                )

                # ------------------------------------------------
                # BOTÃƒÆ’O PRÃƒâ€œXIMO
                # ------------------------------------------------

                botao = wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.ID,
                            "btn_next1",
                        )
                    )
                )

                print(
                    "[CAIXA] Clicando em PrÃƒÂ³ximo..."
                )

                botao.click()

                print(
                    "[CAIXA] Aguardando download..."
                )

                # ------------------------------------------------
                # ESPERA ARQUIVO
                # ------------------------------------------------

                arquivo = self.esperar_download(
                    uf,
                    timeout=120,
                )

                if not arquivo:
                    raise RuntimeError(
                        "Download nÃƒÂ£o apareceu na pasta."
                    )

                print(
                    f"[CAIXA] Arquivo encontrado: "
                    f"{arquivo.name}"
                )

                # ------------------------------------------------
                # VALIDA
                # ------------------------------------------------

                if not self.validar_csv(arquivo):

                    # Se for HTML/CAPTCHA, mostra o problema
                    try:
                        with open(
                            arquivo,
                            "r",
                            encoding="utf-8-sig",
                            errors="ignore",
                        ) as f:
                            inicio = (
                                f.read(500)
                            )
                    except Exception:
                        inicio = ""

                    raise RuntimeError(
                        "O arquivo baixado nÃƒÂ£o ÃƒÂ© um "
                        "CSV vÃƒÂ¡lido da CAIXA. "
                        f"InÃƒÂ­cio: {inicio[:200]!r}"
                    )

                # ------------------------------------------------
                # RENOMEIA
                # ------------------------------------------------

                arquivo_final = self.renomear_arquivo(
                    arquivo,
                    uf,
                )

                tamanho_mb = (
                    arquivo_final.stat().st_size
                    / (1024 * 1024)
                )

                print(
                    f"[CAIXA] OK: {uf} "
                    f"({tamanho_mb:.2f} MB)"
                )

                return {
                    "uf": uf,
                    "sucesso": True,
                    "arquivo": str(arquivo_final),
                    "status": 200,
                    "tamanho_bytes": (
                        arquivo_final.stat().st_size
                    ),
                }

            except Exception as erro:

                ultimo_erro = str(erro)

                print(
                    f"[CAIXA] ERRO {uf}: "
                    f"{ultimo_erro}"
                )

                if tentativa < tentativas:
                    espera = 3 * tentativa

                    print(
                        f"[CAIXA] Aguardando "
                        f"{espera}s antes de tentar novamente..."
                    )

                    time.sleep(espera)

        return {
            "uf": uf,
            "sucesso": False,
            "erro": ultimo_erro,
        }

    # ============================================================
    # BAIXA TODOS
    # ============================================================

    def baixar_todos(
        self,
        tentativas=3,
        intervalo=2.0,
    ):
        """
        Baixa as 27 listas da CAIXA.
        """

        inicio = time.time()

        sucesso = []
        falhas = []

        print()
        print("=" * 60)
        print("ATUALIZAÃƒâ€¡ÃƒÆ’O DAS LISTAS DA CAIXA")
        print("=" * 60)
        print()

        try:
            self.criar_driver()

            print(
                "[CAIXA] Chrome iniciado."
            )

            for uf in self.UFS:

                resultado = self.baixar_estado(
                    uf,
                    tentativas=tentativas,
                )

                if resultado["sucesso"]:
                    sucesso.append(uf)

                else:
                    falhas.append(
                        {
                            "uf": uf,
                            "erro": resultado.get(
                                "erro",
                                "Erro desconhecido",
                            ),
                        }
                    )

                time.sleep(intervalo)

        finally:

            if self.driver:
                print()
                print(
                    "[CAIXA] Encerrando Chrome..."
                )

                try:
                    self.driver.quit()
                except Exception:
                    pass

                self.driver = None

        duracao = time.time() - inicio

        print()
        print("=" * 60)
        print("RESULTADO")
        print("=" * 60)

        print(
            f"Estados baixados: "
            f"{len(sucesso)}/{len(self.UFS)}"
        )

        print(
            f"Tempo total: "
            f"{duracao:.1f} segundos"
        )

        if sucesso:
            print()
            print("OK:")
            print(
                ", ".join(sucesso)
            )

        if falhas:
            print()
            print("FALHAS:")

            for falha in falhas:
                print(
                    f" - {falha['uf']}: "
                    f"{falha['erro']}"
                )

        print()

        return {
            "total": len(self.UFS),
            "sucesso": sucesso,
            "falhas": falhas,
            "duracao_segundos": duracao,
        }


if __name__ == "__main__":

    downloader = CaixaDownloader()

    downloader.baixar_todos()
