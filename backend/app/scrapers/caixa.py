import csv
import os
import re
import time
from datetime import datetime
import unicodedata
from urllib.parse import urljoin
from collections import Counter

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from app.scrapers.base import BaseScraper
from app.schemas.imovel_scraper import ImovelScraper


class CaixaScraper(BaseScraper):

    def __init__(self):
        self.bloqueado = False
        self.driver = None

    def coletar_imagens(self, url):
        """Coleta imagens e datas da pÃƒÂ¡gina de detalhe da Caixa."""

        if not url:
            return {
                "imagens": [],
                "data_primeiro_leilao": None,
                "data_segundo_leilao": None,
            }

        return self._coletar_detalhes_com_selenium(url)

        pagina = BeautifulSoup(resposta.text, "html.parser")
        imagens = self._extrair_imagens_da_pagina(pagina, resposta.url)
        data_primeiro_leilao, data_segundo_leilao = self._extrair_datas_da_pagina(pagina)

        return {
            "imagens": imagens,
            "data_primeiro_leilao": data_primeiro_leilao,
            "data_segundo_leilao": data_segundo_leilao,
        }

    def extrair_datas_leilao(self, url):
        """Extrai somente as datas quando esta consulta for necessÃƒÂ¡ria isoladamente."""

        if not url:
            return None, None

        try:
            resposta = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )

            resposta.raise_for_status()

            if self._pagina_bloqueada(resposta.text):
                detalhes = self._coletar_detalhes_com_selenium(url)
                return (
                    detalhes["data_primeiro_leilao"],
                    detalhes["data_segundo_leilao"],
                )

            pagina = BeautifulSoup(resposta.text, "html.parser")
            return self._extrair_datas_da_pagina(pagina)

        except Exception as erro:
            print("[CAIXA] Erro ao extrair datas:", erro)
            return None, None


    @staticmethod
    def _pagina_bloqueada(texto):
        if not texto:
            return True

        texto = texto.lower()

        marcadores_bloqueio = [
            "radware bot manager",
            "validate.perfdrive.com",
            "access denied",
            "request blocked",
        ]

        return any(
            marcador in texto
            for marcador in marcadores_bloqueio
        )

    def _coletar_detalhes_com_selenium(self, url):
        """Consulta a pÃƒÂ¡gina de detalhe usando uma sessÃƒÂ£o Selenium reutilizÃƒÂ¡vel."""

        for tentativa in range(1, 4):
            try:
                if not self.driver:
                    options = Options()
                    options.add_argument("--start-maximized")
                    options.add_argument("--disable-gpu")
                    options.add_argument("--no-sandbox")
                    options.add_argument("--disable-dev-shm-usage")
                    options.add_argument("--window-size=1920,1080")

                    self.driver = webdriver.Chrome(options=options)
                    self.driver.set_page_load_timeout(30)

                print(
                    f"[CAIXA] Selenium consulta detalhe "
                    f"(tentativa {tentativa}/3): {url}"
                )

                self.driver.get(url)

                WebDriverWait(self.driver, 15).until(
                    lambda navegador: navegador.find_element(
                        "tag name", "body"
                    ).text.strip()
                )

                pagina = BeautifulSoup(
                    self.driver.page_source,
                    "html.parser"
                )

                texto = pagina.get_text(" ", strip=True)
                pagina_source = self.driver.page_source.lower()

                # SÃƒÂ³ considera bloqueio quando houver marcador forte.
                # NÃƒÂ£o usamos o texto do body, pois a Caixa pode conter
                # termos que geram falso positivo.
                marcadores_bloqueio_forte = [
                    "radware bot manager",
                    "access denied",
                    "request blocked",
                ]

                bloqueado = any(
                    marcador in pagina_source
                    for marcador in marcadores_bloqueio_forte
                )

                if bloqueado:
                    print(
                        f"[CAIXA] Bloqueio real detectado "
                        f"(tentativa {tentativa}/3)."
                    )

                    if self.driver:
                        self.driver.quit()
                        self.driver = None

                    if tentativa < 3:
                        espera = 5 * tentativa
                        print(
                            f"[CAIXA] Aguardando {espera}s "
                            f"antes de recriar a sessÃƒÂ£o..."
                        )
                        time.sleep(espera)

                    continue

                imagens = self._extrair_imagens_da_pagina(
                    pagina,
                    self.driver.current_url
                )

                (
                    data_primeiro_leilao,
                    data_segundo_leilao
                ) = self._extrair_datas_da_pagina(pagina)

                return {
                    "imagens": imagens,
                    "data_primeiro_leilao": data_primeiro_leilao,
                    "data_segundo_leilao": data_segundo_leilao,
                }

            except Exception as erro:
                print(
                    f"[CAIXA] Erro Selenium "
                    f"(tentativa {tentativa}/3): {erro}"
                )

                if self.driver:
                    try:
                        self.driver.quit()
                    except Exception:
                        pass

                    self.driver = None

                if tentativa < 3:
                    time.sleep(3 * tentativa)

        return {
            "imagens": [],
            "data_primeiro_leilao": None,
            "data_segundo_leilao": None,
        }

    @staticmethod

    def _extrair_imagens_da_pagina(pagina, url_base):

        """Extrai as URLs reais das fotos da pÃƒÂ¡gina de detalhe da Caixa."""

        imagens = []


        for tag in pagina.select("img"):

            candidatos = []


            # URL diretamente no src.

            src = tag.get("src")

            if src:

                candidatos.append(src)


            # Algumas pÃƒÂ¡ginas da Caixa colocam a foto no onclick:

            # preview.src="/fotos/Fxxxxxxxxxxxxx21.jpg"

            onclick = tag.get("onclick") or ""


            encontrados = re.findall(

                r"""preview\.src\s*=\s*["']([^"']+)["']""",

                onclick,

                re.IGNORECASE,

            )


            candidatos.extend(encontrados)


            for candidato in candidatos:

                imagem = urljoin(url_base, candidato).strip()


                if "/fotos/" not in imagem.lower():

                    continue


                if imagem not in imagens:

                    imagens.append(imagem)


        return imagens



    @staticmethod
    def _extrair_datas_da_pagina(pagina):
        texto_pagina = re.sub(r"\s+", " ", pagina.get_text(" ", strip=True))

        padroes = {
            "primeiro": [
                r"1[Ã‚ÂºÃ‚Â°o]?\s*Leil[aÃƒÂ£]o[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
                r"Primeiro\s+Leil[aÃƒÂ£]o[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
                r"Data[^0-9]{0,50}1[Ã‚ÂºÃ‚Â°o]?\s*Leil[aÃƒÂ£]o[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
            ],
            "segundo": [
                r"2[Ã‚ÂºÃ‚Â°o]?\s*Leil[aÃƒÂ£]o[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
                r"Segundo\s+Leil[aÃƒÂ£]o[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
                r"Data[^0-9]{0,50}2[Ã‚ÂºÃ‚Â°o]?\s*Leil[aÃƒÂ£]o[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
            ],
        }

        def encontrar_data(lista_padroes):
            for padrao in lista_padroes:
                match = re.search(padrao, texto_pagina, re.IGNORECASE)
                if match:
                    return datetime.strptime(match.group(1), "%d/%m/%Y").date()
            return None

        return encontrar_data(padroes["primeiro"]), encontrar_data(padroes["segundo"])

    def _limpar(self, valor):
        if valor is None:
            return ""
        return str(valor).strip()

    def _normalizar_coluna(self, valor):
        if valor is None:
            return ""

        texto = str(valor).strip().lower()

        correcoes = {
            "ÃƒÆ’Ã‚Â¡": "ÃƒÂ¡", "ÃƒÆ’Ã‚Â©": "ÃƒÂ©", "ÃƒÆ’Ã‚Â­": "ÃƒÂ­", "ÃƒÆ’Ã‚Â³": "ÃƒÂ³", "ÃƒÆ’Ã‚Âº": "ÃƒÂº",
            "ÃƒÆ’Ã‚Â£": "ÃƒÂ£", "ÃƒÆ’Ã‚Âµ": "ÃƒÂµ", "ÃƒÆ’Ã‚Â¢": "ÃƒÂ¢", "ÃƒÆ’Ã‚Âª": "ÃƒÂª", "ÃƒÆ’Ã‚Â´": "ÃƒÂ´",
            "ÃƒÆ’Ã‚Â§": "ÃƒÂ§", "ÃƒÆ’": "ÃƒÂ ",
        }

        for antigo, novo in correcoes.items():
            texto = texto.replace(antigo, novo)

        texto = texto.replace("Ã‚Âº", "o").replace("Ã‚Â°", "o")
        texto = unicodedata.normalize("NFKD", texto)

        texto = "".join(
            caractere for caractere in texto if not unicodedata.combining(caractere)
        )

        texto = re.sub(r"[^a-z0-9\s]", " ", texto)
        return re.sub(r"\s+", " ", texto).strip()

    def _numero(self, valor):
        if valor is None:
            return None

        texto = str(valor).strip()
        if not texto:
            return None

        texto = texto.replace("R$", "").replace("r$", "").strip()
        texto = re.sub(r"[^0-9,.\-]", "", texto)

        if not texto:
            return None

        try:
            if "," in texto and "." in texto:
                if texto.rfind(",") > texto.rfind("."):
                    texto = texto.replace(".", "").replace(",", ".")
                else:
                    texto = texto.replace(",", "")
            elif "," in texto:
                texto = texto.replace(",", ".")

            return float(texto)
        except (ValueError, TypeError):
            return None

    def _extrair_tipo(self, descricao):
        texto = self._normalizar_coluna(descricao)

        tipos = [
            ("apartamento", "Apartamento"),
            ("casa", "Casa"),
            ("terreno", "Terreno"),
            ("sala comercial", "Sala Comercial"),
            ("sala", "Sala"),
            ("loja", "Loja"),
            ("galpao", "GalpÃƒÂ£o"),
            ("predio", "PrÃƒÂ©dio"),
            ("fazenda", "Fazenda"),
            ("chacara", "ChÃƒÂ¡cara"),
            ("sitio", "SÃƒÂ­tio"),
            ("sobrado", "Sobrado"),
            ("comercial", "Comercial"),
            ("vaga", "Vaga"),
            ("garagem", "Garagem"),
            ("rural", "Rural"),
        ]

        for palavra, tipo in tipos:
            if palavra in texto:
                return tipo

        return ""

    def _encontrar_coluna(self, mapa, nomes):
        for nome in nomes:
            nome_normalizado = self._normalizar_coluna(nome)
            if nome_normalizado in mapa:
                return mapa[nome_normalizado]
        return None

    def _encontrar_cabecalho(self, linhas):
        for indice, linha in enumerate(linhas):
            if not linha:
                continue

            valores = [self._normalizar_coluna(valor) for valor in linha]
            texto = " ".join(valores)

            tem_imovel = any(
                term in texto
                for term in ["n do imovel", "no do imovel", "numero do imovel", "numero imovel", "imovel"]
            )
            tem_uf = "uf" in valores
            tem_cidade = "cidade" in valores or "municipio" in valores

            if tem_imovel and tem_uf and tem_cidade:
                return indice
        return None

    def _mapear_colunas(self, cabecalho):
        mapa = {}
        for indice, coluna in enumerate(cabecalho):
            nome = self._normalizar_coluna(coluna)
            if nome:
                mapa[nome] = indice
        return mapa

    def _valor_coluna(self, linha, mapa, nomes):
        indice = self._encontrar_coluna(mapa, nomes)
        if indice is None or indice >= len(linha):
            return ""
        return self._limpar(linha[indice])

    def _ler_csv(self, caminho_csv):
        if not os.path.exists(caminho_csv):
            return []

        linhas = None
        delimitador = ";"

        try:
            # A Caixa estÃƒÂ¡ fornecendo os CSVs em UTF-8.
            # Tentamos UTF-8 primeiro para preservar acentos.
            with open(caminho_csv, "r", encoding="utf-8-sig", newline="") as arquivo:
                leitor = csv.reader(arquivo, delimiter=";")
                linhas = list(leitor)

        except UnicodeDecodeError:
            # Fallback para arquivos antigos em Latin-1
            try:
                with open(caminho_csv, "r", encoding="latin1", newline="") as arquivo:
                    leitor = csv.reader(arquivo, delimiter=";")
                    linhas = list(leitor)

            except Exception as erro:
                print(f"[CAIXA] Erro ao ler CSV: {erro}")
                return []

        except Exception as erro:
            print(f"[CAIXA] Erro ao ler CSV: {erro}")
            return []

        if not linhas:
            return []

        # Localiza o cabeÃƒÂ§alho real
        cabecalho_indice = self._encontrar_cabecalho(linhas)

        if cabecalho_indice is None:
            print(f"[CAIXA] CabeÃƒÂ§alho nÃƒÂ£o encontrado: {caminho_csv}")
            print("[CAIXA] Primeiras linhas:")

            for i, linha in enumerate(linhas[:10], start=1):
                print(i, linha)

            return []

        cabecalho = linhas[cabecalho_indice]

        # Mapeia as colunas
        mapa = self._mapear_colunas(cabecalho)

        dados_imoveis = linhas[cabecalho_indice + 1:]

        print(
            f"DEBUG CSV: {os.path.basename(caminho_csv)} "
            f"-> cabeÃƒÂ§alho na linha {cabecalho_indice + 1}, "
            f"{len(dados_imoveis)} imÃƒÂ³veis"
        )

        return dados_imoveis, mapa, cabecalho_indice

    def _processar_csv(self, caminho_csv):
        leitura = self._ler_csv(caminho_csv)
        if not leitura:
            return []

        dados_imoveis, mapa, _ = leitura
        resultados = []

        for contador, linha in enumerate(dados_imoveis, start=1):
            try:
                if not linha or len(linha) < 2:
                    continue

                uf = self._valor_coluna(linha, mapa, ["uf", "estado uf", "sigla uf"])
                numero_imovel = self._valor_coluna(
                    linha, mapa, ["nÃ‚Âº do imÃƒÂ³vel", "nÃ‚Â° do imÃƒÂ³vel", "numero do imovel", "nÃƒÂºmero do imovel", "numero imovel", "imovel"]
                )
                cidade = self._valor_coluna(linha, mapa, ["cidade", "municipio", "municÃƒÂ­pio"])
                endereco = self._valor_coluna(linha, mapa, ["endereco", "endereÃƒÂ§o", "bairro - cidade", "bairro cidade", "bairro"])

                valor_avaliacao = self._numero(self._valor_coluna(linha, mapa, ["avaliacao", "valor de avaliacao", "valor avaliacao", "avaliaÃƒÂ§ÃƒÂ£o"]))
                preco = self._numero(self._valor_coluna(linha, mapa, ["preco", "preÃƒÂ§o", "valor de venda", "valor venda"]))
                desconto = self._numero(self._valor_coluna(linha, mapa, ["desconto", "valor desconto"]))

                data_primeiro_leilao = self._valor_coluna(linha, mapa, ["data primeiro leilao", "data primeiro leilÃƒÂ£o", "primeiro leilao", "primeiro leilÃƒÂ£o"])
                data_segundo_leilao = self._valor_coluna(linha, mapa, ["data segundo leilao", "data segundo leilÃƒÂ£o", "segundo leilao", "segundo leilÃƒÂ£o"])

                if isinstance(data_primeiro_leilao, str):
                    data_primeiro_leilao = data_primeiro_leilao.strip() or None
                if isinstance(data_segundo_leilao, str):
                    data_segundo_leilao = data_segundo_leilao.strip() or None

                modalidade = self._valor_coluna(linha, mapa, ["modalidade", "modalidade de venda", "modalidade da venda"])
                descricao = self._valor_coluna(linha, mapa, ["descricao", "descriÃƒÂ§ÃƒÂ£o", "detalhes do imovel", "detalhes do imÃƒÂ³vel"])
                url = self._valor_coluna(linha, mapa, ["link de acesso", "url", "link", "link do imovel", "link do imÃƒÂ³vel"])

                modalidade = self._valor_coluna(
                    linha,
                    mapa,
                    ["modalidade", "modalidade de venda", "modalidade de venda"]
                )

                descricao = self._valor_coluna(
                    linha,
                    mapa,
                    ["descricao", "descriÃƒÂ§ÃƒÂ£o", "detalhes do imÃƒÂ³vel"]
                )

                url = self._valor_coluna(
                    linha,
                    mapa,
                    ["link de acesso", "url", "link", "link do imÃƒÂ³vel"]
                )

                if modalidade != "LeilÃƒÂ£o SFI - Edital ÃƒÅ¡nico":
                    continue

                print("URL ANTES:", repr(url))

                # Normaliza URL da CAIXA.
                # O CSV pode trazer:
                # [https://...](https://...)
                # ou simplesmente:
                # https://...
                if url:
                    url = str(url).strip()

                    # Extrai a URL de dentro do Markdown
                    match_url = re.search(r"\((https?://[^)]+)\)", url)

                    if match_url:
                        url = match_url.group(1)
                    else:
                        # Caso jÃƒÂ¡ seja uma URL normal
                        match_url = re.search(r"https?://[^\s\]\)]+", url)
                        url = match_url.group(0) if match_url else None

                print("URL DEPOIS:", repr(url))

                # ============================================================
                # DADOS DE DETALHE
                # ============================================================
                # NÃƒÆ’O consultar a pÃƒÂ¡gina individual da Caixa durante a
                # importaÃƒÂ§ÃƒÂ£o do CSV. Isso evita bloqueio do Radware.
                #
                # As pÃƒÂ¡ginas de detalhe serÃƒÂ£o enriquecidas posteriormente
                # em uma etapa separada e controlada.

                imagem = None

                # Preserva eventual informaÃƒÂ§ÃƒÂ£o existente no CSV.
                # Normalmente a lista da Caixa nÃƒÂ£o fornece essas datas.
                # Nesse caso permanecem None para posterior enriquecimento.


                if not uf and not cidade:
                    continue

                texto_para_tipo = f"{descricao} {modalidade} {endereco}"
                tipo = self._extrair_tipo(texto_para_tipo)

                if tipo and cidade:
                    titulo = f"{tipo} - {cidade}"
                elif cidade:
                    titulo = cidade
                elif tipo:
                    titulo = tipo
                else:
                    titulo = f"ImÃƒÂ³vel {numero_imovel}" if numero_imovel else "ImÃƒÂ³vel Caixa"

                # ExtraÃƒÂ§ÃƒÂ£o de detalhes (ÃƒÂ¡rea, quartos, banheiros, vagas)
                area_util = None
                quartos = None
                banheiros = None
                vagas = None

                texto_descricao = descricao or ""

                # ============================================================
                # EXTRAÃƒâ€¡ÃƒÆ’O DA ÃƒÂREA
                # ============================================================

                area_util = None

                texto_area = re.sub(
                    r"\s+",
                    " ",
                    texto_descricao
                ).strip()

                texto_area_normalizado = (
                    unicodedata.normalize("NFKD", texto_area)
                    .encode("ascii", "ignore")
                    .decode("ascii")
                )

                tipo_normalizado = (tipo or "").strip().lower()

                eh_terreno = tipo_normalizado in {
                    "terreno",
                    "lote",
                }

                # 1. ÃƒÂREA PRIVATIVA

                padroes_area_privativa = [
                    # 55.94 de AREA PRIVATIVA
                    r"(\d+(?:[.,]\d+)?)\s*de\s*area\s+privativa",

                    # 55.94 M2 de AREA PRIVATIVA
                    r"(\d+(?:[.,]\d+)?)\s*m(?:2|Ã‚Â²)?\s*de\s*area\s+privativa",

                    # AREA PRIVATIVA: 55.94 M2
                    r"area\s+privativa\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*m(?:2|Ã‚Â²)?",

                    # AREA PRIVATIVA: 55.94
                    r"area\s+privativa\s*[:\-]?\s*(\d+(?:[.,]\d+)?)",
                ]

                if not eh_terreno:
                    for padrao in padroes_area_privativa:
                        match = re.search(
                            padrao,
                            texto_area_normalizado,
                            re.IGNORECASE
                        )

                        if match:
                            valor_area_privativa = self._numero(match.group(1))

                            if valor_area_privativa and valor_area_privativa > 0:
                                area_util = valor_area_privativa
                                break

                # 2. ÃƒÂREA TOTAL - FALLBACK
                # SÃƒÂ³ usa a ÃƒÂ¡rea total se ela for maior que zero.
                if area_util is None or area_util <= 0:
                    padroes_area_total = [
                        # 55.94 de AREA TOTAL
                        r"(\d+(?:[.,]\d+)?)\s*de\s*area\s+total",

                        # 55.94 M2 de AREA TOTAL
                        r"(\d+(?:[.,]\d+)?)\s*m(?:2|Ãƒâ€šÃ‚Â²)?\s*de\s*area\s+total",

                        # AREA TOTAL: 55.94 M2
                        r"area\s+total\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*m(?:2|Ãƒâ€šÃ‚Â²)?",

                        # AREA TOTAL: 55.94
                        r"area\s+total\s*[:\-]?\s*(\d+(?:[.,]\d+)?)",
                    ]

                    for padrao in padroes_area_total:
                        match = re.search(
                            padrao,
                            texto_area_normalizado,
                            re.IGNORECASE
                        )

                        if match:
                            valor_area_total = self._numero(match.group(1))

                            if valor_area_total and valor_area_total > 0:
                                area_util = valor_area_total
                                break

                # 3. ÃƒÂREA DO TERRENO - FALLBACK
                # Usada principalmente para terrenos quando nÃƒÂ£o existe
                # ÃƒÂ¡rea privativa nem ÃƒÂ¡rea total vÃƒÂ¡lida.
                if area_util is None or area_util <= 0:
                    padroes_area_terreno = [
                        # 5717.66 de AREA DO TERRENO
                        r"(\d+(?:[.,]\d+)?)\s*de\s*area\s+do\s+terreno",

                        # AREA DO TERRENO: 5717.66
                        r"area\s+do\s+terreno\s*[:\-]?\s*(\d+(?:[.,]\d+)?)",

                        # 5717.66 M2 DE AREA DO TERRENO
                        r"(\d+(?:[.,]\d+)?)\s*m(?:2|Ãƒâ€šÃ‚Â²)?\s*de\s*area\s+do\s+terreno",
                    ]

                    for padrao in padroes_area_terreno:
                        match = re.search(
                            padrao,
                            texto_area_normalizado,
                            re.IGNORECASE
                        )

                        if match:
                            valor_area_terreno = self._numero(match.group(1))

                            if valor_area_terreno and valor_area_terreno > 0:
                                area_util = valor_area_terreno
                                break


                match = re.search(r"(\d+)\s*qto(?:\(s\))?", texto_descricao, re.IGNORECASE) or re.search(r"(\d+)\s+quarto(?:s)?", texto_descricao, re.IGNORECASE)
                if match:
                    quartos = int(match.group(1))

                match = (
                    re.search(r"\b(\d+)\s*vaga", texto_descricao, re.IGNORECASE)
                    or re.search(r"\bvagas?\s*[:\-]\s*(\d+)\b", texto_descricao, re.IGNORECASE)
                    or re.search(r"\bgaragem\s+(?:para|com)\s+(\d+)\s*(?:ve[ií]culos?|carros?)?\b", texto_descricao, re.IGNORECASE)
                    or re.search(r"\b(\d+)\s*(?:ve[ií]culos?)\s*(?:de\s+garagem)?\b", texto_descricao, re.IGNORECASE)
                )
                if match:
                    vagas = int(match.group(1))

                match = re.search(r"(\d+)\s*(?:wc|banheiro(?:\(s\))?)", texto_descricao, re.IGNORECASE)
                if match:
                    banheiros = int(match.group(1))
                elif re.search(r"\bwc\b", texto_descricao, re.IGNORECASE):
                    banheiros = 1

                # ============================================================
                # COLETA FOTOS E DATAS DA PÃƒÂGINA DE DETALHE DA CAIXA
                # ============================================================

                imovel = ImovelScraper(
                    titulo=titulo,
                    tipo=tipo,
                    endereco=endereco,
                    cidade=cidade,
                    estado=uf,
                    valor_avaliacao=valor_avaliacao,
                    valor_leilao=preco,
                    desconto=desconto,
                    data_primeiro_leilao=data_primeiro_leilao,
                    data_segundo_leilao=data_segundo_leilao,
                    area_util=area_util,
                    quartos=quartos,
                    banheiros=banheiros,
                    vagas=vagas,
                    url=url,
                    imagem=imagem,
                    imagens=[imagem] if imagem else [],
                    modalidade=modalidade,
                    fonte="Caixa",
                )

                resultados.append(imovel)

            except Exception as erro:
                print(f"[CAIXA] Erro ao processar linha {contador}: {erro}")
                continue

        return resultados

    def executar(self):
        resultados = []
        self.bloqueado = False

        pasta_dados = os.path.join(os.path.dirname(__file__), "dados")

        if not os.path.exists(pasta_dados):
            print("ERRO: pasta de dados nÃƒÂ£o encontrada.")
            return []

        arquivos_csv = [
            os.path.join(pasta_dados, f)
            for f in os.listdir(pasta_dados)
            if os.path.isfile(os.path.join(pasta_dados, f)) and f.lower().endswith(".csv")
        ]
        arquivos_csv.sort()

        if not arquivos_csv:
            print("ERRO: nenhum arquivo CSV encontrado.")
            return []

        for caminho_csv in arquivos_csv:
            try:
                print("DEBUG CSV:", caminho_csv)

                encontrados = self._processar_csv(caminho_csv)

                print(
                    "DEBUG CSV RESULTADO:",
                    os.path.basename(caminho_csv),
                    "->",
                    len(encontrados),
                    "imÃƒÂ³veis"
                )

                resultados.extend(encontrados)

            except Exception as erro:
                print(
                    f"ERRO AO PROCESSAR CSV "
                    f"{os.path.basename(caminho_csv)}: {erro}"
                )
                continue

        # Removendo duplicados por chave ÃƒÂºnica
        unicos = []
        vistos = set()
        for imovel in resultados:
            chave = (
                getattr(imovel, "estado", "") or "",
                getattr(imovel, "cidade", "") or "",
                getattr(imovel, "endereco", "") or "",
                getattr(imovel, "titulo", "") or "",
            )
            if chave not in vistos:
                vistos.add(chave)
                unicos.append(imovel)

            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None

        return unicos

    def baixar_pagina(self):
        return ""


if __name__ == "__main__":
    scraper = CaixaScraper()
    resultados = scraper.executar()
    print(f"\nTotal processado: {len(resultados)}")
