from app.scrapers.caixa import CaixaScraper

class ScraperManager:

    def __init__(self):

      self.scrapers = {
          "caixa": CaixaScraper(),
      }

    def executar(self, fontes: list[str]):
        resultados = []

        for nome in fontes:
            scraper = self.scrapers.get(nome)

            if not scraper:

               continue

            dados = scraper.executar()

            if dados:
               resultados.extend(dados)

        return resultados
