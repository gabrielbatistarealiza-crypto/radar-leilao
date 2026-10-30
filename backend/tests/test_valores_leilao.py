"""Valores do 1.º e 2.º leilão lidos do edital (Anexo II) e o lance mínimo usado no site.

A lista da Caixa só traz um preço, que nos leilões SFI é igual à avaliação; por
isso, sem edital, esses imóveis apareciam com desconto 0. Sem rede.
"""
from datetime import date

import pytest

from app.models.imovel import Imovel
from app.services import caixa_datas_edital as ce

URL = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"
EDITAL = "https://venda-imoveis.caixa.gov.br/editais/EL00560226CPARE.PDF"
N1, N2, N3 = "8787714663143", "8555533895378", "1444404561864"

# Excerto com a forma do edital 0056 (texto extraído pelo pypdf).
ANEXO = (
    "1.1 – Data e Hora da Sessão do 1º Leilão: 14/12/2026 às 10:00h.\n"
    "1.2 – Data e Hora da Sessão do 2º Leilão: 17/12/2026 às 10:00h.\n"
    "Anexo II – RELAÇÃO DE IMÓVEIS\n"
    " EMP  ENDEREÇO  BAIRRO  DESCRIÇÃO  NÚMERO DO BEM  VALOR DE \nVENDA \n1º LEILÃO \n(R$) \n"
    " VALOR DE \nVENDA \n2º LEILÃO \n(R$) \n VALOR DE  \nAVALIAÇÃ \nO \n(R$) \n"
    "402  RES CIDADE DE COIMBRA AVENIDA MANOEL ANTONIO PERES N. 2440 APTO. 202\n"
    "GARAGEM. IPTU: 1271121 \nMATRÍCULA: 6402 OFÍCIO: 3. \n"
    f"{N1}  149.014,00  111.258,07  140.000,00  \n"
    "9 TERRA BRASILIS APTO. 403 COZINHA. IPTU: \n2015827 MATRÍCULA: \n23647 OFÍCIO: 2. \n"
    f"{N2}  140.961,96  211.179,78  135.000,00  \n"
    f"{N3}  Arrematado \n"
)


@pytest.fixture(autouse=True)
def pdf_de_texto_e_hoje(monkeypatch):
    monkeypatch.setattr(ce, "ler_edital", lambda corpo: ce.interpretar_texto_edital(corpo[5:].decode()))
    monkeypatch.setattr(ce, "_hoje", lambda: date(2026, 10, 30))


def imovel(fabrica, numero, **campos):
    base = dict(fonte="Caixa", url=URL.format(numero), modalidade="Leilão SFI - Edital Único",
                valor_avaliacao=140000.0, valor_leilao=140000.0, desconto=0.0, area=47.73,
                data_primeiro_leilao=None, data_segundo_leilao=None)
    base.update(campos)
    return fabrica.imovel(**base)


def test_le_os_tres_valores_de_cada_imovel():
    e = ce.interpretar_texto_edital(ANEXO)
    assert e.valores == {
        N1: (149014.0, 111258.07, 140000.0),
        N2: (140961.96, 211179.78, 135000.0),
    }
    assert N3 in e.numeros_sem_venda and N3 not in e.valores


def test_iptu_e_matricula_nao_sao_confundidos_com_valores():
    e = ce.interpretar_texto_edital(ANEXO)
    assert e.numeros == {N1, N2}


def test_numero_com_valores_diferentes_fica_sem_valores():
    texto = ANEXO + f"{N1}  150.000,00  100.000,00  140.000,00  \n"
    e = ce.interpretar_texto_edital(texto)
    assert N1 not in e.valores and N1 in e.numeros and N2 in e.valores


def test_edital_antigo_so_com_dois_valores_continua_a_dar_datas():
    texto = ANEXO.replace("  140.000,00  \n", "  \n", 1)
    e = ce.interpretar_texto_edital(texto)
    assert N1 in e.numeros and N1 not in e.valores


def test_aplicar_edital_grava_os_valores_e_o_lance_minimo(sessao, fabrica):
    a = imovel(fabrica, N1)
    b = imovel(fabrica, N2, valor_avaliacao=135000.0, valor_leilao=135000.0)

    r = ce.aplicar_edital_local(sessao, b"%PDF-" + ANEXO.encode(), EDITAL, gravar=True)

    sessao.expire_all()
    assert r["gravado"] and r["valores_de_leilao_gravados"] == 2 and r["valores_no_edital"] == 2
    assert (a.valor_primeiro_leilao, a.valor_segundo_leilao) == (149014.0, 111258.07)
    assert a.valor_lance == 111258.07
    assert a.desconto_atual == pytest.approx(20.53, abs=0.01)
    # Quando a dívida faz o 2.º leilão ficar acima do 1.º, o lance mínimo é o do 1.º.
    assert b.valor_lance == 140961.96 and b.desconto_atual < 0
    assert a.valor_leilao == 140000.0  # o preço da lista fica como estava


def test_ensaio_nao_grava_valores(sessao, fabrica):
    a = imovel(fabrica, N1)

    r = ce.aplicar_edital_local(sessao, b"%PDF-" + ANEXO.encode(), EDITAL, gravar=False)

    sessao.expire_all()
    assert not r["gravado"] and r["valores_de_leilao_gravados"] == 1
    assert a.valor_segundo_leilao is None and a.valor_lance == 140000.0


def test_sem_edital_continua_o_preco_e_desconto_da_lista(fabrica):
    a = imovel(fabrica, N1, valor_avaliacao=200000.0, valor_leilao=150000.0, desconto=25.0)
    assert a.valor_lance == 150000.0 and a.desconto_atual == 25.0
    assert a.economia_m2 == pytest.approx(50000.0 / 47.73)


def test_expressao_sql_do_lance_minimo_igual_a_do_python(sessao, fabrica):
    casos = [
        imovel(fabrica, "1", valor_primeiro_leilao=149014.0, valor_segundo_leilao=111258.07),
        imovel(fabrica, "2", valor_primeiro_leilao=140961.96, valor_segundo_leilao=211179.78),
        imovel(fabrica, "3"),
        imovel(fabrica, "4", valor_segundo_leilao=90000.0),
    ]
    sql = dict(sessao.query(Imovel.id, Imovel.valor_lance).all())
    for i in casos:
        assert sql[i.id] == pytest.approx(i.valor_lance)


def test_api_usa_o_lance_minimo_no_desconto_e_na_ordenacao(http, fabrica):
    sem_edital = imovel(fabrica, "11", titulo="Sem edital")
    com_edital = imovel(fabrica, "12", titulo="Com edital",
                        valor_primeiro_leilao=149014.0, valor_segundo_leilao=111258.07)

    r = http.get("/imoveis/", params={"ordenar": "desconto", "direcao": "desc", "status_leilao": "todos"})

    assert r.status_code == 200
    itens = r.json()["items"]
    assert [i["id"] for i in itens][:2] == [com_edital.id, sem_edital.id]
    primeiro = itens[0]
    assert primeiro["valor_leilao"] == 111258.07 and primeiro["valor_lista"] == 140000.0
    assert primeiro["valor_primeiro_leilao"] == 149014.0 and primeiro["valor_segundo_leilao"] == 111258.07
    assert primeiro["desconto"] == pytest.approx(20.53, abs=0.01)
    assert itens[1]["desconto"] == 0.0 and itens[1]["valor_segundo_leilao"] is None

    so_com_desconto = http.get("/imoveis/", params={"desconto_minimo": 10, "status_leilao": "todos"}).json()
    assert [i["id"] for i in so_com_desconto["items"]] == [com_edital.id]
