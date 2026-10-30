"""A importação da lista só lê os CSV das UFs descarregadas nessa execução.

Em 29/10/2026 a descarga parou em AL (REDIRECIONADO) e a rotina reimportou os
CSV de 21/10 que estavam no disco para as outras 26 UFs. Sem rede.
"""
import pytest

from app.models.imovel import Imovel
from app.schemas.imovel_scraper import ImovelScraper
from app.scrapers.caixa import CaixaScraper
from app.services import scraper_service
from app.services.scraper_service import ScraperService

URL = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"
CABECALHO = (
    "N° do imóvel;UF;Cidade;Bairro;Endereço;Preço;Valor de avaliação;Desconto;"
    "Financiamento;Descrição;Modalidade de venda;Link de acesso"
)
TODAS = list(scraper_service.CaixaDownloader.UFS)


def escrever_csv(pasta, uf, numeros):
    linhas = [
        ";".join([str(n), uf, "CIDADE", "CENTRO", f"RUA A, {n}", "100.000,00", "200.000,00",
                  "50,00", "Sim", "Casa, 2 qto(s).", "Leilão SFI - Edital Único", URL.format(n)])
        for n in numeros
    ]
    texto = ("Lista de imóveis da CAIXA;;;;;;;;;;;\nGerado em 21/10/2026;;;;;;;;;;;\n\n"
             + CABECALHO + "\n" + "\n".join(linhas) + "\n")
    (pasta / f"Lista_imoveis_{uf}.csv").write_text(texto, encoding="utf-8-sig")


def numeros(imoveis):
    return sorted(int(i.url.rsplit("=", 1)[1]) for i in imoveis)


# ------------------------------------------------------------ leitor de CSV

@pytest.fixture()
def pasta(tmp_path):
    escrever_csv(tmp_path, "SP", [1, 2])
    escrever_csv(tmp_path, "RJ", [3])
    escrever_csv(tmp_path, "AL", [4])
    return tmp_path


def ler(pasta, ufs):
    scraper = CaixaScraper()
    scraper.pasta_dados = str(pasta)
    scraper.ufs_permitidas = ufs
    return scraper.executar()


def test_sem_filtro_le_todos_os_csv(pasta):
    assert numeros(ler(pasta, None)) == [1, 2, 3, 4]


def test_le_so_as_ufs_permitidas_sem_distinguir_maiusculas(pasta):
    assert numeros(ler(pasta, {"sp", "AL"})) == [1, 2, 4]


def test_lista_de_ufs_vazia_nao_le_nada(pasta):
    assert ler(pasta, set()) == []


# ------------------------------------------------------- atualizar_lista_caixa

@pytest.fixture()
def rodar(monkeypatch, sessao):
    chamadas = []

    def _rodar(sucesso, bloqueado=False):
        class DownloaderFalso:
            UFS = TODAS

            def baixar_todos(self, *args, **kwargs):
                r = {"sucesso": list(sucesso), "falhas": [], "pedidos": len(sucesso)}
                if bloqueado:
                    r.update(bloqueado=True, paragem="REDIRECIONADO", uf_bloqueada="AL")
                return r

        class ScraperFalso:
            def __init__(self):
                self.ufs_permitidas = None

            def executar(self):
                chamadas.append(self.ufs_permitidas)
                ufs = self.ufs_permitidas or {"SP"}
                return [
                    ImovelScraper(titulo=f"Imóvel {uf}", url=URL.format(100 + i), estado=uf, fonte="Caixa")
                    for i, uf in enumerate(sorted(ufs))
                ]

        monkeypatch.setattr(scraper_service, "CaixaDownloader", DownloaderFalso)
        monkeypatch.setattr(scraper_service, "CaixaScraper", ScraperFalso)
        monkeypatch.setattr(ScraperService, "preparar_fila_fotos_caixa", lambda self, i: {"pendentes": 0})
        return ScraperService(sessao).atualizar_lista_caixa(remover=False)

    _rodar.chamadas = chamadas
    return _rodar


def test_bloqueio_a_meio_importa_so_as_ufs_ja_descarregadas(rodar, sessao):
    r = rodar(["AC"], bloqueado=True)

    assert rodar.chamadas == [{"AC"}]
    assert r["ufs_importadas"] == ["AC"]
    assert r["imoveis_atualizados"] == 1
    assert sessao.query(Imovel).count() == 1


def test_sem_nenhuma_uf_descarregada_nao_importa_nada(rodar, sessao, fabrica):
    fabrica.imovel(url=URL.format(1), fonte="Caixa", valor_leilao=5.0)

    r = rodar([], bloqueado=True)

    assert rodar.chamadas == []  # nem chega a ler CSV
    assert r["ufs_importadas"] == [] and r["imoveis_atualizados"] == 0
    assert r["imoveis_removidos"] == 0
    sessao.expire_all()
    assert sessao.query(Imovel).one().valor_leilao == pytest.approx(5.0)


def test_descarga_completa_importa_as_27_ufs(rodar):
    r = rodar(TODAS)

    assert rodar.chamadas == [set(TODAS)]
    assert r["ufs_importadas"] == sorted(TODAS)


def test_importacao_manual_continua_a_ler_todos_os_csv(monkeypatch, sessao):
    lidas = []

    class ScraperFalso:
        def __init__(self):
            self.ufs_permitidas = None

        def executar(self):
            lidas.append(self.ufs_permitidas)
            return []

    monkeypatch.setattr(scraper_service, "CaixaScraper", ScraperFalso)
    ScraperService(sessao).executar_scraper_caixa()
    assert lidas == [None]
