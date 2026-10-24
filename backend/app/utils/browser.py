from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
import os
import re

class CaixaBloqueioError(Exception):
    """Indica que a Caixa bloqueou/protegeu o acesso à página."""
    pass

class Browser:
    def __init__(self):
        self.playwright = None
        self.navegador = None
        self.pagina = None

    def iniciar(self):
        """Inicia uma sessão Playwright reutilizável."""
        if self.pagina:
            return

        self.playwright = sync_playwright().start()

        self.navegador = self.playwright.chromium.launch(
            headless=os.getenv("BROWSER_HEADLESS", "false").lower() in {"1", "true", "yes"}
        )

        self.pagina = self.navegador.new_page(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        print("[BROWSER] Sessão Playwright iniciada.")

    def fechar(self):
        """Fecha a sessão Playwright reutilizável."""
        try:
            if self.pagina:
                self.pagina.close()
        except Exception:
            pass

        try:
            if self.navegador:
                self.navegador.close()
        except Exception:
            pass

        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass

        self.pagina = None
        self.navegador = None
        self.playwright = None

        print("[BROWSER] Sessão Playwright encerrada.")

    def coletar_imagens_galeria_sessao(self, url: str):
        """Coleta imagens usando uma sessão Playwright já aberta."""

        if not url:
            return [], 0

        if not self.pagina:
            raise RuntimeError(
                "Sessão Playwright não iniciada. "
                "Execute Browser.iniciar() antes da coleta."
            )

        pagina = self.pagina

        pagina.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        pagina.wait_for_selector(
            "body",
            timeout=10000,
        )

        # Dá tempo para a galeria terminar de carregar.
        pagina.wait_for_timeout(3000)

        galeria = pagina.locator("#galeria-imagens")

        if galeria.count() == 0:
            texto = pagina.locator("body").inner_text()

            sinais_bloqueio = (
                "Estamos detectando comportamento malicioso no acesso",
                "access denied",
                "request blocked",
                "we have detected unusual traffic",
                "verify you are human",
                "captcha",
            )

            # A página normal pode carregar o script do Radware. Só marcamos
            # bloqueio quando há mensagem de proteção no texto visível.
            bloqueado = any(
                sinal.lower() in texto.lower()
                for sinal in sinais_bloqueio
            )

            if bloqueado:
                print("[CAIXA] BLOQUEIO/PROTEÇÃO DETECTADO.")
                raise CaixaBloqueioError(
                    "Caixa bloqueou/protegeu o acesso à página."
                )

            print("[GALERIA] #galeria-imagens não encontrada.")
            return [], 0

        print("[GALERIA] #galeria-imagens encontrada.")

        fontes = galeria.locator("img").evaluate_all(
            """
            imagens => imagens.map(img => ({
                src: img.getAttribute("src"),
                dataSrc: img.getAttribute("data-src"),
                dataOriginal: img.getAttribute("data-original"),
                srcset: img.getAttribute("srcset"),
                onclick: img.getAttribute("onclick"),
                alt: img.getAttribute("alt")
            }))
            """
        )

        print(
            f"[GALERIA] Elementos <img> encontrados: {len(fontes)}"
        )

        imagens = []

        def adicionar_imagem(candidato):
            if not candidato:
                return

            candidato = candidato.strip()

            if not candidato:
                return

            imagem = urljoin(pagina.url, candidato)

            if "/fotos/" not in imagem:
                return

            if not imagem.lower().split("?")[0].endswith(
                (".jpg", ".jpeg")
            ):
                return

            if imagem not in imagens:
                imagens.append(imagem)
                print(f"[FOTO] {imagem}")

        for fonte in fontes:
            adicionar_imagem(fonte.get("src"))
            adicionar_imagem(fonte.get("dataSrc"))
            adicionar_imagem(fonte.get("dataOriginal"))

            srcset = fonte.get("srcset")

            if srcset:
                for item in srcset.split(","):
                    parte = item.strip().split(" ")[0]

                    if parte:
                        adicionar_imagem(parte)

            onclick = fonte.get("onclick")

            if onclick:
                encontrados = re.findall(
                    r"""['"]([^'"]*/fotos/[^'"]+\.(?:jpg|jpeg)(?:\?[^'"]*)?)['"]""",
                    onclick,
                    flags=re.IGNORECASE,
                )

                for encontrado in encontrados:
                    adicionar_imagem(encontrado)

        print(
            f"[GALERIA] Total de imagens coletadas: {len(imagens)}"
        )

        return imagens, len(imagens)

    def coletar_imagens_galeria(self, url: str):
        """
        Método original mantido para compatibilidade.
        Abre uma sessão exclusiva para uma única coleta.
        """

        if not url:
            return [], 0

        self.iniciar()

        try:
            return self.coletar_imagens_galeria_sessao(url)
        finally:
            self.fechar()

    # Browser.abrir() foi removido: pedia para resolver o CAPTCHA à mão e
    # continuar, o que contraria a regra de parar ao primeiro bloqueio.
    # Não era chamado por nenhum código.
