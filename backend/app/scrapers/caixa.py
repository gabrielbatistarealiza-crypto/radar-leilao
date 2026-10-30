import csv
import os
import re
import time
from datetime import date, datetime
import unicodedata
from urllib.parse import urljoin
from collections import Counter

import requests
from bs4 import BeautifulSoup
from bs4.element import PreformattedString
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from app.scrapers.base import BaseScraper
from app.schemas.imovel_scraper import ImovelScraper


class CaixaFalhaTecnicaError(Exception):
    """A página não pôde ser lida (Chrome indisponível, timeouts repetidos...).

    É diferente de "página lida e sem datas": o imóvel deve ser tentado de novo.
    """


class CaixaScraper(BaseScraper):
    _bloqueio_ate = 0.0
    _tempo_bloqueio_segundos = 600

    def __init__(self):
        self.bloqueado = False
        self.driver = None
        self.pasta_dados = os.path.join(os.path.dirname(__file__), "dados")
        # None = todos os CSV da pasta; senão só os destas UFs (Lista_imoveis_<UF>.csv).
        self.ufs_permitidas = None

    def coletar_imagens(self, url):
        """Coleta imagens e datas da pÃƒÂ¡gina de detalhe da Caixa."""

        if not url:
            return {
                "imagens": [],
                "data_primeiro_leilao": None,
                "data_segundo_leilao": None,
                "data_licitacao_aberta": None,
            }

        return self._coletar_detalhes_com_selenium(url)

    def extrair_datas_leilao(self, url):
        """Extrai somente as datas quando esta consulta for necessÃƒÂ¡ria isoladamente."""

        if not url:
            return None, None, None
        if time.monotonic() < self.__class__._bloqueio_ate:
            self.bloqueado = True
            return None, None, None

        datas_estaticas = (None, None, None)
        try:
            resposta = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )

            resposta.raise_for_status()

            pagina = BeautifulSoup(resposta.text, "html.parser")
            texto_visivel = self._texto_visivel(pagina)
            titulo_pagina = pagina.title.get_text(" ", strip=True) if pagina.title else ""
            # Aqui só os marcadores contam: uma resposta vazia a requests pode ser
            # só a página montada por JavaScript, e o Selenium decide a seguir.
            if self._tem_marcador_bloqueio(f"{titulo_pagina} {texto_visivel}"):
                self.__class__._bloqueio_ate = time.monotonic() + self._tempo_bloqueio_segundos
                self.bloqueado = True
                return None, None, None

            datas_estaticas = self._extrair_datas_da_pagina(pagina)

        except Exception as erro:
            print("[CAIXA] Erro ao extrair datas com requests:", erro)

        # A página pode carregar as datas por JavaScript, ou a resposta simples
        # pode estar bloqueada/incompleta. Nesse caso, tenta ler o DOM renderizado.
        # Leilão (1º e 2º) e licitação aberta não aparecem juntos na mesma
        # página: com um dos conjuntos completo, não abre o Selenium, que é o
        # acesso que a CAIXA bloqueia.
        primeiro, segundo, licitacao_aberta = datas_estaticas
        if (primeiro and segundo) or licitacao_aberta:
            return datas_estaticas

        try:
            detalhes = self._coletar_detalhes_com_selenium(url)
        except Exception as erro:
            print("[CAIXA] Erro ao extrair datas com Selenium:", erro)
            if not any(datas_estaticas):
                raise CaixaFalhaTecnicaError(str(erro)) from erro
            return datas_estaticas

        if detalhes.get("falha_tecnica") and not any(datas_estaticas):
            # Sem leitura válida da página: não é "sem datas", é "não consegui ver".
            raise CaixaFalhaTecnicaError(
                "Selenium não conseguiu abrir a página de detalhe."
            )

        datas_renderizadas = (
            detalhes["data_primeiro_leilao"],
            detalhes["data_segundo_leilao"],
            detalhes["data_licitacao_aberta"],
        )
        return tuple(
            data_renderizada if data_renderizada is not None else data_estatica
            for data_estatica, data_renderizada in zip(
                datas_estaticas, datas_renderizadas
            )
        )


    # Mesmos sinais usados em app/utils/browser.py, mais os já existentes aqui.
    # Devem ser procurados só no texto visível: a página normal também carrega
    # o script do Radware.
    _MARCADORES_BLOQUEIO = (
        "access denied",
        "request blocked",
        "your request has been blocked",
        "we have detected unusual traffic",
        "verify you are human",
        "confirme que você é humano",
        "verificação de segurança",
        "estamos detectando comportamento malicioso",
        "radware bot manager",
        "captcha",
    )

    @staticmethod
    def _texto_visivel(pagina):
        """Texto da página sem scripts, estilos, comentários e doctype."""
        ocultos = {"script", "style", "noscript", "template"}
        partes = []
        for trecho in pagina.find_all(string=True):
            if isinstance(trecho, PreformattedString):
                continue
            if trecho.parent is not None and trecho.parent.name in ocultos:
                continue
            texto = trecho.strip()
            if texto:
                partes.append(texto)
        return re.sub(r"\s+", " ", " ".join(partes)).strip()

    @classmethod
    def _tem_marcador_bloqueio(cls, texto):
        texto = (texto or "").lower()
        return any(marcador in texto for marcador in cls._MARCADORES_BLOQUEIO)

    @classmethod
    def _pagina_bloqueada(cls, texto):
        if not texto or not texto.strip():
            return True
        return cls._tem_marcador_bloqueio(texto)

    def _coletar_detalhes_com_selenium(self, url):
        """Consulta a pÃƒÂ¡gina de detalhe usando uma sessÃƒÂ£o Selenium reutilizÃƒÂ¡vel."""

        # Só passa a False quando a página foi lida ou um bloqueio foi visto.
        falha_tecnica = True

        for tentativa in range(1, 4):
            try:
                if not self.driver:
                    options = Options()
                    if os.getenv("BROWSER_HEADLESS", "true").lower() in {"1", "true", "yes"}:
                        options.add_argument("--headless=new")
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

                texto = self._texto_visivel(pagina)
                titulo_pagina = self.driver.title or ""
                bloqueado = self._pagina_bloqueada(f"{titulo_pagina} {texto}")

                if bloqueado:
                    print(
                        f"[CAIXA] Bloqueio real detectado "
                        f"(tentativa {tentativa}/3)."
                    )
                    self.bloqueado = True
                    falha_tecnica = False
                    self.__class__._bloqueio_ate = time.monotonic() + self._tempo_bloqueio_segundos

                    if self.driver:
                        self.driver.quit()
                        self.driver = None

                    # Repetir a consulta após um bloqueio só aumenta a carga.
                    break

                imagens = self._extrair_imagens_da_pagina(
                    pagina,
                    self.driver.current_url
                )

                (
                    data_primeiro_leilao,
                    data_segundo_leilao,
                    data_licitacao_aberta,
                ) = self._extrair_datas_da_pagina(pagina)

                return {
                    "imagens": imagens,
                    "data_primeiro_leilao": data_primeiro_leilao,
                    "data_segundo_leilao": data_segundo_leilao,
                    "data_licitacao_aberta": data_licitacao_aberta,
                    "falha_tecnica": False,
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
            "data_licitacao_aberta": None,
            "falha_tecnica": falha_tecnica,
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
                r"1[º°o]?\s*Leil[aã]o[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
                r"Primeiro\s+Leil[aã]o[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
                r"Data[^0-9]{0,50}1[º°o]?\s*Leil[aã]o[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
            ],
            "segundo": [
                r"2[º°o]?\s*Leil[aã]o[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
                r"Segundo\s+Leil[aã]o[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
                r"Data[^0-9]{0,50}2[º°o]?\s*Leil[aã]o[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
            ],
            "licitacao_aberta": [
                r"Data\s+da\s+Licita[cç][aã]o\s+Aberta[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
                r"Licita[cç][aã]o\s+Aberta[^0-9]{0,100}(\d{2}/\d{2}/\d{4})",
            ],
        }

        def encontrar_data(lista_padroes):
            # Uma data impossível (ex.: 31/02) não pode invalidar as outras nem
            # levantar erro: é ignorada e procura-se a ocorrência seguinte.
            for padrao in lista_padroes:
                for match in re.finditer(padrao, texto_pagina, re.IGNORECASE):
                    try:
                        return datetime.strptime(match.group(1), "%d/%m/%Y").date()
                    except ValueError:
                        continue
            return None

        return (
            encontrar_data(padroes["primeiro"]),
            encontrar_data(padroes["segundo"]),
            encontrar_data(padroes["licitacao_aberta"]),
        )

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

    @staticmethod
    def _interpretar_sim_nao(valor):
        """Converte "Sim"/"Não" do CSV em True/False.

        Qualquer outro valor (vazio, "-", texto inesperado) vira None, que
        significa "não informado". Não confunda com False ("não aceita").
        """
        if valor is None:
            return None
        texto = unicodedata.normalize("NFKD", str(valor).strip().lower())
        texto = "".join(c for c in texto if not unicodedata.combining(c))
        if texto in {"sim", "s", "yes", "true", "1"}:
            return True
        if texto in {"nao", "n", "no", "false", "0"}:
            return False
        return None

    @staticmethod
    def _normalizar_data(valor):
        """Converte datas comuns da fonte CAIXA para date sem rejeitar o imóvel."""
        if isinstance(valor, datetime):
            return valor.date()
        if isinstance(valor, date):
            return valor
        if valor is None:
            return None

        texto = str(valor).strip()
        if not texto:
            return None

        # ISO ou datetime ISO (YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS).
        if re.match(r"^\d{4}-\d{2}-\d{2}", texto):
            try:
                return date.fromisoformat(texto[:10])
            except ValueError:
                return None

        # Formato brasileiro, aceitando também hora após a data.
        match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", texto)
        if not match:
            return None
        dia, mes, ano = (int(parte) for parte in match.groups())
        try:
            return date(ano, mes, dia)
        except ValueError:
            return None

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
            ("galpao", "Galpão"),
            ("predio", "Prédio"),
            ("fazenda", "Fazenda"),
            ("chacara", "Chácara"),
            ("sitio", "Sítio"),
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
            with open(
                caminho_csv,
                "r",
                encoding="utf-8-sig",
                newline=""
            ) as arquivo:
                leitor = csv.reader(arquivo, delimiter=delimitador)
                linhas = list(leitor)

        except UnicodeDecodeError:
            try:
                with open(
                    caminho_csv,
                    "r",
                    encoding="latin1",
                    newline=""
                ) as arquivo:
                    leitor = csv.reader(arquivo, delimiter=delimitador)
                    linhas = list(leitor)

            except Exception as erro:
                print(f"[CAIXA] Erro ao ler CSV: {erro}")
                return []

        if not linhas:
            return []

        # Corrige textos com dupla codificação
        def corrigir_mojibake(texto):
            if not isinstance(texto, str):
                return texto

            for _ in range(2):
                # Só tenta desfazer uma codificação quebrada quando
                # existem sinais típicos de mojibake.
                sinais_mojibake = (
                    "Ã",
                    "Â",
                    "Æ",
                    "Ð",
                    "Ñ",
                    "â",
                    "ð",
                    "ï¿½",
                )

                if not any(sinal in texto for sinal in sinais_mojibake):
                    break

                try:
                    texto_novo = texto.encode("cp1252").decode("utf-8")

                    if texto_novo == texto:
                        break

                    texto = texto_novo

                except (UnicodeEncodeError, UnicodeDecodeError):
                    break

            return texto

        # Corrige todas as células
        linhas = [
            [corrigir_mojibake(celula) for celula in linha]
            for linha in linhas
        ]

        # Procura o cabeçalho real do CSV
        indice_cabecalho = None

        for indice, linha in enumerate(linhas):
            texto_linha = " ".join(
                str(celula).strip().lower()
                for celula in linha
            )

            # O CSV da Caixa possui colunas como UF, cidade,
            # endereço, avaliação, preço etc.
            if (
                ("uf" in texto_linha or "estado" in texto_linha)
                and ("cidade" in texto_linha or "município" in texto_linha)
                and ("preço" in texto_linha or "preco" in texto_linha)
            ):
                indice_cabecalho = indice
                break

        if indice_cabecalho is None:
            print(
                f"ERRO CSV: cabeçalho não encontrado em "
                f"{os.path.basename(caminho_csv)}"
            )
            return []

        cabecalho = linhas[indice_cabecalho]

        # Monta o mapa:
        # nome normalizado da coluna -> índice
        mapa = {}

        for indice, nome in enumerate(cabecalho):
            nome_normalizado = self._normalizar_coluna(nome)

            if nome_normalizado:
                mapa[nome_normalizado] = indice

        # Tudo depois do cabeçalho são os imóveis
        dados_imoveis = linhas[indice_cabecalho + 1:]

        print(
            f"DEBUG CSV: {os.path.basename(caminho_csv)} -> "
            f"cabeçalho na linha {indice_cabecalho + 1}, "
            f"{len(dados_imoveis)} imóveis"
        )

        return dados_imoveis, mapa, indice_cabecalho

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
                aceita_financiamento = self._interpretar_sim_nao(
                    self._valor_coluna(linha, mapa, ["financiamento", "aceita financiamento"])
                )

                data_primeiro_leilao = self._normalizar_data(
                    self._valor_coluna(
                        linha,
                        mapa,
                        ["data primeiro leilao", "data primeiro leilÃƒÂ£o", "primeiro leilao", "primeiro leilÃƒÂ£o"],
                    )
                )
                data_segundo_leilao = self._normalizar_data(
                    self._valor_coluna(
                        linha,
                        mapa,
                        ["data segundo leilao", "data segundo leilÃƒÂ£o", "segundo leilao", "segundo leilÃƒÂ£o"],
                    )
                )
                data_licitacao_aberta = self._normalizar_data(
                    self._valor_coluna(
                        linha,
                        mapa,
                        [
                            "data licitacao aberta",
                            "data da licitacao aberta",
                            "licitacao aberta",
                        ],
                    )
                )

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

                # Só "Leilão SFI - Edital Único". A comparação ignora acentos,
                # maiúsculas, hífenes e espaços (decisão 6): uma pequena mudança
                # no rótulo da Caixa não deve fazer a importação trazer 0 imóveis.
                # Grava-se sempre o rótulo canónico.
                if self._normalizar_coluna(modalidade) != "leilao sfi edital unico":
                    continue
                modalidade = "Leilão SFI - Edital Único"

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
                    titulo = f"Imóvel {numero_imovel}" if numero_imovel else "Imóvel Caixa"

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
                    data_licitacao_aberta=data_licitacao_aberta,
                    area_util=area_util,
                    quartos=quartos,
                    banheiros=banheiros,
                    vagas=vagas,
                    url=url,
                    imagem=imagem,
                    imagens=[imagem] if imagem else [],
                    modalidade=modalidade,
                    aceita_financiamento=aceita_financiamento,
                    fonte="Caixa",
                )

                resultados.append(imovel)

            except Exception as erro:
                print(f"[CAIXA] Erro ao processar linha {contador}: {erro}")
                continue

        return resultados

    @staticmethod
    def _remover_duplicados(imoveis):
        """Remove repetições reais da lista.

        A identidade de um imóvel da Caixa é o número dele (hdnimovel, na URL).
        Só quando não há URL usa estado + cidade + endereço + título. Usar só o
        endereço juntaria unidades diferentes do mesmo prédio ou loteamento.
        """
        unicos = []
        vistos = set()
        for imovel in imoveis:
            url = getattr(imovel, "url", None) or ""
            achado = re.search(r"hdnimovel=(\d+)", url, re.IGNORECASE)
            if achado:
                chave = ("id", achado.group(1))
            else:
                chave = (
                    "endereco",
                    getattr(imovel, "estado", "") or "",
                    getattr(imovel, "cidade", "") or "",
                    getattr(imovel, "endereco", "") or "",
                    getattr(imovel, "titulo", "") or "",
                )
            if chave not in vistos:
                vistos.add(chave)
                unicos.append(imovel)
        return unicos

    def executar(self):
        resultados = []
        self.bloqueado = False

        pasta_dados = self.pasta_dados

        if not os.path.exists(pasta_dados):
            print("ERRO: pasta de dados nÃƒÂ£o encontrada.")
            return []

        arquivos_csv = [
            os.path.join(pasta_dados, f)
            for f in os.listdir(pasta_dados)
            if os.path.isfile(os.path.join(pasta_dados, f)) and f.lower().endswith(".csv")
        ]
        arquivos_csv.sort()

        if self.ufs_permitidas is not None:
            nomes = {f"LISTA_IMOVEIS_{uf.strip().upper()}.CSV" for uf in self.ufs_permitidas}
            arquivos_csv = [c for c in arquivos_csv if os.path.basename(c).upper() in nomes]

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
                    "imóveis"
                )

                resultados.extend(encontrados)

            except Exception as erro:
                print(
                    f"ERRO AO PROCESSAR CSV "
                    f"{os.path.basename(caminho_csv)}: {erro}"
                )
                continue

        unicos = self._remover_duplicados(resultados)

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
