"""Leitura do CSV da Caixa (app/scrapers/caixa.py). Não usa rede nem navegador."""
import pytest

from app.schemas.imovel_scraper import ImovelScraper
from app.scrapers.caixa import CaixaScraper

SFI = "Leilão SFI - Edital Único"
URL = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"
CABECALHO = (
    "N° do imóvel;UF;Cidade;Bairro;Endereço;Preço;Valor de avaliação;Desconto;"
    "Financiamento;Descrição;Modalidade de venda;Link de acesso"
)
DESCRICAO = "Apartamento, 56.00 de área total, 2 qto(s), 1 WC, 1 vaga(s) de garagem."


def linha(numero, financiamento="Sim", modalidade=SFI, endereco=None, cidade="CAMPINAS"):
    return ";".join(
        [
            str(numero), "SP", cidade, "CENTRO", endereco or f"RUA A, {numero}",
            "100.000,00", "200.000,00", "50,00", financiamento, DESCRICAO,
            modalidade, URL.format(numero),
        ]
    )


def sem_coluna_financiamento(texto):
    partes = texto.split(";")
    return ";".join(partes[:8] + partes[9:])


def processar(tmp_path, linhas, cabecalho=CABECALHO):
    # A Caixa coloca linhas de apresentação antes do cabeçalho.
    texto = (
        "Lista de imóveis da CAIXA;;;;;;;;;;;\nGerado em 21/10/2026;;;;;;;;;;;\n\n"
        + cabecalho + "\n" + "\n".join(linhas) + "\n"
    )
    caminho = tmp_path / "Lista_imoveis_SP.csv"
    caminho.write_text(texto, encoding="utf-8-sig")
    return CaixaScraper()._processar_csv(str(caminho))


# ------------------------------------------------------------ Sim / Não

@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("Sim", True), ("SIM", True), (" sim ", True),
        ("Não", False), ("NÃO", False), ("nao", False),
        ("", None), ("-", None), ("talvez", None), (None, None),
    ],
)
def test_interpretar_sim_nao(valor, esperado):
    assert CaixaScraper._interpretar_sim_nao(valor) is esperado


def test_le_a_coluna_financiamento(tmp_path):
    resultado = processar(tmp_path, [linha(1, "Sim"), linha(2, "Não"), linha(3, "")])
    assert [i.aceita_financiamento for i in resultado] == [True, False, None]


def test_csv_sem_a_coluna_financiamento_deixa_o_dado_como_desconhecido(tmp_path):
    cabecalho = sem_coluna_financiamento(CABECALHO)
    resultado = processar(tmp_path, [sem_coluna_financiamento(linha(1))], cabecalho)
    assert len(resultado) == 1
    assert resultado[0].aceita_financiamento is None


# ---------------------------------------------------------- conversão

def test_importa_so_leilao_sfi_edital_unico(tmp_path):
    resultado = processar(
        tmp_path,
        [linha(1), linha(2, modalidade="Venda Online"), linha(3, modalidade="Licitação Aberta")],
    )
    assert [i.url for i in resultado] == [URL.format(1)]


@pytest.mark.parametrize("rotulo", [
    "Leilão SFI - Edital Único", "LEILÃO SFI - EDITAL ÚNICO", "Leilao SFI - Edital Unico",
    "Leilão SFI – Edital Único", "  Leilão  SFI -  Edital Único ",
])
def test_rotulo_sfi_com_variacoes_continua_a_ser_importado(tmp_path, rotulo):
    # Decisão 6: acentos, maiúsculas, travessões e espaços não mudam a modalidade.
    [imovel] = processar(tmp_path, [linha(1, modalidade=rotulo)])
    assert imovel.modalidade == SFI


@pytest.mark.parametrize("rotulo", ["Leilão SFI", "Leilão SFI - Edital Único 2", "Venda Direta Online"])
def test_outras_modalidades_continuam_de_fora(tmp_path, rotulo):
    assert processar(tmp_path, [linha(1, modalidade=rotulo)]) == []


def test_converte_os_campos_basicos(tmp_path):
    [imovel] = processar(tmp_path, [linha(1)])
    assert imovel.estado == "SP" and imovel.cidade == "CAMPINAS"
    assert imovel.tipo == "Apartamento"
    assert imovel.titulo == "Apartamento - CAMPINAS"
    assert imovel.valor_leilao == pytest.approx(100000.0)
    assert imovel.valor_avaliacao == pytest.approx(200000.0)
    assert imovel.desconto == pytest.approx(50.0)
    assert imovel.quartos == 2 and imovel.vagas == 1
    assert imovel.modalidade == SFI and imovel.fonte == "Caixa"


def test_ocupacao_e_fgts_nao_sao_inventados(tmp_path):
    # O CSV da Caixa não traz esses dados; o scraper não pode chutar.
    [imovel] = processar(tmp_path, [linha(1)])
    assert not hasattr(imovel, "ocupado") or imovel.ocupado is None
    assert not hasattr(imovel, "aceita_fgts") or imovel.aceita_fgts is None


# ------------------------------------------------------- deduplicação

def test_unidades_diferentes_no_mesmo_endereco_nao_sao_duplicadas(tmp_path):
    resultado = processar(
        tmp_path, [linha(1, endereco="RUA X, 10"), linha(2, endereco="RUA X, 10")]
    )
    assert len(CaixaScraper._remover_duplicados(resultado)) == 2


def test_mesmo_numero_de_imovel_e_duplicado(tmp_path):
    resultado = processar(tmp_path, [linha(1), linha(1)])
    assert len(CaixaScraper._remover_duplicados(resultado)) == 1


def test_sem_url_a_chave_e_endereco_cidade_estado_e_titulo():
    base = dict(titulo="T", cidade="C", estado="SP", endereco="E")
    iguais = [ImovelScraper(**base), ImovelScraper(**base)]
    assert len(CaixaScraper._remover_duplicados(iguais)) == 1

    diferentes = [ImovelScraper(**base), ImovelScraper(**dict(base, endereco="OUTRO"))]
    assert len(CaixaScraper._remover_duplicados(diferentes)) == 2
