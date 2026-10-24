from datetime import date, timedelta

import pytest

MODALIDADE_PADRAO = "Leilão SFI - Edital Único"


@pytest.fixture()
def catalogo(fabrica):
    """Cinco imóveis com características diferentes (datas relativas a hoje)."""
    hoje = date.today()
    return {
        # ativo, 50% de desconto, o maior e o mais barato
        "A": fabrica.imovel(
            titulo="A Campinas", cidade="Campinas", estado="SP", tipo="Casa",
            valor_avaliacao=200000.0, valor_leilao=100000.0, area=100.0, quartos=3,
            data_primeiro_leilao=hoje + timedelta(days=10),
        ),
        # ativo, 25% de desconto
        "B": fabrica.imovel(
            titulo="B São Paulo", cidade="São Paulo", estado="SP", tipo="Apartamento",
            valor_avaliacao=400000.0, valor_leilao=300000.0, area=60.0, quartos=2,
            data_primeiro_leilao=hoje + timedelta(days=40),
        ),
        # encerrado (data no passado), 20% de desconto
        "C": fabrica.imovel(
            titulo="C Curitiba", cidade="Curitiba", estado="PR", tipo="Casa",
            valor_avaliacao=100000.0, valor_leilao=80000.0, area=40.0, quartos=1,
            data_primeiro_leilao=hoje - timedelta(days=5),
        ),
        # sem data de leilão e sem área, 50% de desconto
        "D": fabrica.imovel(
            titulo="D Recife", cidade="Recife", estado="PE", tipo="Apartamento",
            valor_avaliacao=300000.0, valor_leilao=150000.0, area=None, quartos=None,
            data_primeiro_leilao=None,
        ),
        # ativo, mas de outra modalidade
        "E": fabrica.imovel(
            titulo="E Venda Direta", cidade="Santos", estado="SP", tipo="Casa",
            modalidade="Venda Direta Online",
            valor_avaliacao=200000.0, valor_leilao=120000.0, area=70.0, quartos=2,
            data_primeiro_leilao=hoje + timedelta(days=20),
        ),
    }


def buscar(http, **params):
    resposta = http.get("/imoveis/", params=params)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def titulos(corpo):
    return [item["titulo"][0] for item in corpo["items"]]


# ------------------------------------------------- padrões da busca

def test_busca_padrao_traz_so_ativos_da_modalidade_padrao(http, catalogo):
    corpo = buscar(http)
    assert sorted(titulos(corpo)) == ["A", "B"]
    assert corpo["total"] == 2


def test_modalidade_vazia_remove_o_filtro_de_modalidade(http, catalogo):
    corpo = buscar(http, modalidade="")
    assert sorted(titulos(corpo)) == ["A", "B", "E"]


def test_status_encerrados(http, catalogo):
    assert titulos(buscar(http, status_leilao="encerrados")) == ["C"]


def test_status_sem_data(http, catalogo):
    assert titulos(buscar(http, status_leilao="sem_data")) == ["D"]


def test_status_todos(http, catalogo):
    corpo = buscar(http, status_leilao="todos", modalidade="")
    assert sorted(titulos(corpo)) == ["A", "B", "C", "D", "E"]


# --------------------------------------------------------- filtros

def test_desconto_minimo(http, catalogo):
    corpo = buscar(http, status_leilao="todos", desconto_minimo=40)
    assert sorted(titulos(corpo)) == ["A", "D"]


def test_valor_maximo(http, catalogo):
    corpo = buscar(http, status_leilao="todos", valor_maximo=100000)
    assert sorted(titulos(corpo)) == ["A", "C"]


def test_faixa_de_area(http, catalogo):
    corpo = buscar(http, status_leilao="todos", area_min=50, area_max=100)
    assert sorted(titulos(corpo)) == ["A", "B"]


def test_quartos(http, catalogo):
    assert titulos(buscar(http, status_leilao="todos", quartos=1)) == ["C"]


def test_estado_e_tipo(http, catalogo):
    corpo = buscar(http, status_leilao="todos", estado="SP", tipo="Casa")
    assert titulos(corpo) == ["A"]  # E também é SP/Casa, mas de outra modalidade


def test_filtros_combinados_sem_resultado(http, catalogo):
    corpo = buscar(http, estado="PR", desconto_minimo=60)
    assert corpo["items"] == []
    assert corpo["total"] == 0
    assert corpo["paginas_totais"] == 0


def test_cidade_ignora_acentos_e_caixa(http, catalogo, eh_postgres):
    if not eh_postgres:
        pytest.skip("usa func.translate, que só existe no PostgreSQL")
    corpo = buscar(http, cidade="sao paulo", status_leilao="todos")
    assert titulos(corpo) == ["B"]


# ------------------------------------------------------ paginação

def test_paginacao(http, catalogo):
    pagina1 = buscar(http, status_leilao="todos", modalidade="", tamanho_pagina=2)
    assert pagina1["total"] == 5
    assert pagina1["paginas_totais"] == 3
    assert len(pagina1["items"]) == 2

    pagina3 = buscar(http, status_leilao="todos", modalidade="", tamanho_pagina=2, pagina=3)
    assert len(pagina3["items"]) == 1

    vista = set()
    for numero in (1, 2, 3):
        pagina = buscar(
            http, status_leilao="todos", modalidade="", tamanho_pagina=2, pagina=numero
        )
        vista.update(item["id"] for item in pagina["items"])
    assert len(vista) == 5  # nenhuma repetição entre páginas


def test_pagina_alem_do_fim_devolve_lista_vazia(http, catalogo):
    corpo = buscar(http, pagina=99)
    assert corpo["items"] == []
    assert corpo["total"] == 2


@pytest.mark.parametrize(
    "params",
    [
        {"pagina": 0},
        {"tamanho_pagina": 0},
        {"tamanho_pagina": 101},
        {"ordenar": "invalido"},
        {"status_leilao": "invalido"},
        {"direcao": "lado"},
    ],
)
def test_parametros_invalidos_retornam_422(http, params):
    assert http.get("/imoveis/", params=params).status_code == 422


# ----------------------------------------------------- ordenação

def test_ordenacao_padrao_e_preco_crescente(http, catalogo):
    assert titulos(buscar(http)) == ["A", "B"]


def test_ordenar_por_preco_decrescente(http, catalogo):
    assert titulos(buscar(http, direcao="desc")) == ["B", "A"]


def test_ordenar_por_desconto_vem_do_maior_para_o_menor(http, catalogo):
    corpo = buscar(http, status_leilao="todos", ordenar="desconto")
    assert titulos(corpo)[-1] == "C"  # 20% é o menor desconto
    assert set(titulos(corpo)[:2]) == {"A", "D"}  # 50%


def test_ordenar_por_area_deixa_sem_area_por_ultimo(http, catalogo):
    corpo = buscar(http, status_leilao="todos", ordenar="area")
    assert titulos(corpo)[0] == "A"
    assert titulos(corpo)[-1] == "D"


def test_ordenar_por_score_coloca_a_melhor_oportunidade_primeiro(http, catalogo, eh_postgres):
    if not eh_postgres:
        pytest.skip("o score faz conta com datas no SQL, validada no PostgreSQL")
    assert titulos(buscar(http, ordenar="score")) == ["A", "B"]


# ------------------------------------------------ formato da resposta

def test_item_traz_os_campos_que_o_frontend_usa(http, catalogo):
    item = buscar(http)["items"][0]
    for campo in (
        "id", "titulo", "tipo", "cidade", "estado", "valor_avaliacao", "valor_leilao",
        "desconto", "area", "quartos", "data_primeiro_leilao", "modalidade",
        "imagem", "imagens", "economia_m2",
    ):
        assert campo in item, campo


def test_fotos_vem_ordenadas_e_a_primeira_vira_imagem_principal(http, fabrica):
    imovel = fabrica.imovel()
    fabrica.foto(imovel, "http://x/2.jpg", ordem=2)
    fabrica.foto(imovel, "http://x/1.jpg", ordem=1)
    item = buscar(http)["items"][0]
    assert item["imagens"] == ["http://x/1.jpg", "http://x/2.jpg"]
    assert item["imagem"] == "http://x/1.jpg"


def test_sem_fotos_usa_a_url_da_imagem_do_imovel(http, fabrica):
    fabrica.imovel(url_imagem="http://x/capa.jpg")
    item = buscar(http)["items"][0]
    assert item["imagens"] == ["http://x/capa.jpg"]
    assert item["imagem"] == "http://x/capa.jpg"


def test_sem_nenhuma_foto(http, fabrica):
    fabrica.imovel()
    item = buscar(http)["items"][0]
    assert item["imagens"] == []
    assert item["imagem"] is None


def test_economia_por_m2(http, fabrica):
    fabrica.imovel(valor_avaliacao=200000.0, valor_leilao=100000.0, area=100.0)
    assert buscar(http)["items"][0]["economia_m2"] == pytest.approx(1000.0)


# ------------------------------------------------- detalhes do imóvel

def test_detalhes_do_imovel(http, fabrica):
    imovel = fabrica.imovel(titulo="Casa X")
    corpo = http.get(f"/imoveis/{imovel.id}")
    assert corpo.status_code == 200
    assert corpo.json()["titulo"] == "Casa X"


def test_imovel_inexistente_retorna_404(http):
    assert http.get("/imoveis/99999").status_code == 404


def test_detalhes_expoem_edital_leiloeiro_e_processo(http, fabrica):
    # Esses campos existem no banco e o frontend os mostra na tela de detalhes.
    imovel = fabrica.imovel(
        link_edital="http://x/edital.pdf", leiloeiro="Leiloeiro Tal", processo="123/2026"
    )
    corpo = http.get(f"/imoveis/{imovel.id}").json()
    assert corpo["link_edital"] == "http://x/edital.pdf"
    assert corpo["leiloeiro"] == "Leiloeiro Tal"
    assert corpo["processo"] == "123/2026"


def test_listagem_tambem_expoe_o_link_do_edital(http, fabrica):
    fabrica.imovel(link_edital="http://x/edital.pdf")
    assert buscar(http)["items"][0]["link_edital"] == "http://x/edital.pdf"


# ------------------------------------------------------ manutenção

def test_rotas_de_manutencao_exigem_administrador(http, cliente, autenticar):
    rota = "/imoveis/manutencao/processar-fila-fotos-caixa"
    assert http.post(rota).status_code == 401
    assert http.post(rota, headers=autenticar(cliente)).status_code == 403


# ------------------------------------- ocupação, FGTS e financiamento

def test_condicoes_de_compra_conhecidas_sao_enviadas(http, fabrica):
    imovel = fabrica.imovel(ocupado=True, aceita_fgts=False, aceita_financiamento=True)
    corpo = http.get(f"/imoveis/{imovel.id}").json()
    assert corpo["ocupado"] is True
    assert corpo["aceita_fgts"] is False
    assert corpo["aceita_financiamento"] is True


def test_condicoes_desconhecidas_chegam_como_nulo(http, fabrica):
    # None = "não informado". O frontend esconde o campo, em vez de mostrar
    # "Desocupado" ou "Não aceita FGTS" para um dado que ninguém sabe.
    # Depende do modelo novo (colunas sem default false) e da migração SQL.
    imovel = fabrica.imovel()
    detalhe = http.get(f"/imoveis/{imovel.id}").json()
    item = buscar(http)["items"][0]
    for resposta in (detalhe, item):
        assert resposta["ocupado"] is None
        assert resposta["aceita_fgts"] is None
        assert resposta["aceita_financiamento"] is None
