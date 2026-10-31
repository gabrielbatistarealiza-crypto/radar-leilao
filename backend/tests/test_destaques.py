"""Vitrine do ecrã de entrada: GET /imoveis/destaques, sem sessão. Sem rede."""
from datetime import date, timedelta


def destaque(fabrica, cidade, desconto, foto=True, **campos):
    i = fabrica.imovel(cidade=cidade, valor_avaliacao=100000.0,
                       valor_leilao=100000.0 * (1 - desconto / 100), desconto=desconto, **campos)
    if foto:
        fabrica.foto(i, f"https://venda-imoveis.caixa.gov.br/fotos/F{i.id}.jpg")
    return i


def test_sem_sessao_devolve_os_maiores_descontos_com_foto(http, fabrica):
    a = destaque(fabrica, "Campinas", 40)
    b = destaque(fabrica, "Santos", 30)
    destaque(fabrica, "Sorocaba", 50, foto=False)  # sem foto: fora

    r = http.get("/imoveis/destaques")

    assert r.status_code == 200
    corpo = r.json()
    assert [d["id"] for d in corpo] == [a.id, b.id]
    assert corpo[0]["desconto"] == 40.0 and corpo[0]["valor_lance"] == 60000.0
    assert corpo[0]["foto"].endswith(f"F{a.id}.jpg") and corpo[0]["cidade"] == "Campinas"
    assert set(corpo[0]) == {"id", "tipo", "cidade", "estado", "foto", "valor_avaliacao",
                             "valor_lance", "desconto", "proximo_leilao"}


def test_uma_cidade_de_cada_vez_e_limite(http, fabrica):
    a = destaque(fabrica, "Campinas", 40)
    destaque(fabrica, "CAMPINAS ", 39)  # mesma cidade: fica de fora
    c = destaque(fabrica, "Santos", 30)

    assert [d["id"] for d in http.get("/imoveis/destaques").json()] == [a.id, c.id]
    assert [d["id"] for d in http.get("/imoveis/destaques", params={"limite": 1}).json()] == [a.id]
    assert http.get("/imoveis/destaques", params={"limite": 50}).status_code == 422


def test_fora_da_lista_leilao_passado_ou_sem_desconto_nao_aparecem(http, fabrica):
    passado = date.today() - timedelta(days=1)
    destaque(fabrica, "A", 40, na_lista=False)
    destaque(fabrica, "B", 40, data_primeiro_leilao=passado, data_segundo_leilao=passado)
    destaque(fabrica, "C", 0)
    ok = destaque(fabrica, "D", 10)

    assert [d["id"] for d in http.get("/imoveis/destaques").json()] == [ok.id]


def test_usa_o_lance_minimo_do_edital(http, fabrica):
    i = destaque(fabrica, "Pelotas", 0, valor_primeiro_leilao=110000.0, valor_segundo_leilao=75000.0)

    d = http.get("/imoveis/destaques").json()[0]

    assert d["id"] == i.id and d["valor_lance"] == 75000.0 and d["desconto"] == 25.0


def test_destaques_nao_e_confundido_com_um_id(http):
    assert http.get("/imoveis/destaques").status_code == 200
