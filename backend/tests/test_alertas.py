from datetime import date, timedelta

import pytest

from app.models.notificacao import Notificacao


def criar_alerta(http, cabecalho, **corpo):
    corpo.setdefault("nome", "Meu alerta")
    return http.post("/alertas", json=corpo, headers=cabecalho)


def correspondencias(http, cabecalho):
    resposta = http.get("/alertas/correspondencias", headers=cabecalho)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def titulos(itens):
    return sorted({item["imovel"]["titulo"] for item in itens})


# ------------------------------------------------------------ critérios

def test_cria_e_lista_alerta(http, cliente, autenticar):
    cabecalho = autenticar(cliente)
    resposta = criar_alerta(http, cabecalho, estado="SP", desconto_minimo=30, alertar_prazos_dias=5)
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["estado"] == "SP" and corpo["alertar_prazos_dias"] == 5 and corpo["ativo"] is True

    lista = http.get("/alertas", headers=cabecalho).json()
    assert [a["id"] for a in lista] == [corpo["id"]]


def test_alerta_exige_login(http):
    assert http.get("/alertas").status_code == 401
    assert http.post("/alertas", json={"nome": "x"}).status_code == 401


@pytest.mark.parametrize(
    "corpo",
    [
        {"nome": ""},
        {"nome": "x", "estado": "SPX"},
        {"nome": "x", "desconto_minimo": 101},
        {"nome": "x", "preco_maximo": 0},
        {"nome": "x", "alertar_prazos_dias": 91},
        {"nome": "x", "roi_minimo": 10},  # ROI sem cenário guardado
    ],
)
def test_alerta_invalido_retorna_422(http, cliente, autenticar, corpo):
    assert http.post("/alertas", json=corpo, headers=autenticar(cliente)).status_code == 422


def test_nome_so_com_espacos_e_recusado(http, cliente, autenticar):
    resposta = criar_alerta(http, autenticar(cliente), nome="   ", estado="SP")
    assert resposta.status_code == 422


def test_atualiza_e_exclui_o_proprio_alerta(http, cliente, autenticar):
    cabecalho = autenticar(cliente)
    alerta = criar_alerta(http, cabecalho, estado="SP").json()

    atualizado = http.put(
        f"/alertas/{alerta['id']}", json={"nome": "Novo nome", "estado": "RJ"}, headers=cabecalho
    )
    assert atualizado.status_code == 200
    assert atualizado.json()["nome"] == "Novo nome" and atualizado.json()["estado"] == "RJ"

    assert http.delete(f"/alertas/{alerta['id']}", headers=cabecalho).status_code == 204
    assert http.get("/alertas", headers=cabecalho).json() == []


def test_ninguem_mexe_no_alerta_de_outra_pessoa(http, cliente, outro_cliente, autenticar):
    alerta = criar_alerta(http, autenticar(cliente), estado="SP").json()
    intruso = autenticar(outro_cliente)

    assert http.get("/alertas", headers=intruso).json() == []
    assert http.put(f"/alertas/{alerta['id']}", json={"nome": "x"}, headers=intruso).status_code == 404
    assert http.delete(f"/alertas/{alerta['id']}", headers=intruso).status_code == 404


# ------------------------------------------------------- correspondências

def test_sem_criterios_nao_ha_correspondencias(http, fabrica, cliente, autenticar):
    fabrica.imovel()
    assert correspondencias(http, autenticar(cliente)) == []


def test_corresponde_por_estado_e_desconto(http, fabrica, cliente, autenticar):
    fabrica.imovel(titulo="Bom", estado="SP", valor_avaliacao=200000.0, valor_leilao=100000.0)
    fabrica.imovel(titulo="Pouco desconto", estado="SP", valor_avaliacao=200000.0, valor_leilao=190000.0)
    fabrica.imovel(titulo="Outro estado", estado="PR", valor_avaliacao=200000.0, valor_leilao=100000.0)
    cabecalho = autenticar(cliente)
    criar_alerta(http, cabecalho, estado="SP", desconto_minimo=30, alertar_prazos_dias=0)

    itens = correspondencias(http, cabecalho)

    assert titulos(itens) == ["Bom"]
    assert itens[0]["corresponde"] is True
    assert any("Desconto" in motivo for motivo in itens[0]["motivos"])


def test_corresponde_por_preco_maximo_e_cidade(http, fabrica, cliente, autenticar):
    fabrica.imovel(titulo="Barato", cidade="Campinas", valor_leilao=100000.0)
    fabrica.imovel(titulo="Caro", cidade="Campinas", valor_leilao=900000.0)
    fabrica.imovel(titulo="Outra cidade", cidade="Santos", valor_leilao=100000.0)
    cabecalho = autenticar(cliente)
    criar_alerta(http, cabecalho, cidade="campinas", preco_maximo=300000, alertar_prazos_dias=0)

    assert titulos(correspondencias(http, cabecalho)) == ["Barato"]


def test_correspondencias_sao_so_do_dono_do_criterio(http, fabrica, cliente, outro_cliente, autenticar):
    fabrica.imovel(estado="SP")
    criar_alerta(http, autenticar(cliente), estado="SP", alertar_prazos_dias=0)
    assert correspondencias(http, autenticar(outro_cliente)) == []


def test_leilao_proximo_de_imovel_que_combina_gera_alerta_de_prazo(http, fabrica, cliente, autenticar):
    fabrica.imovel(
        titulo="Combina e esta perto", estado="SP",
        data_primeiro_leilao=date.today() + timedelta(days=3),
    )
    cabecalho = autenticar(cliente)
    criar_alerta(http, cabecalho, estado="SP", alertar_prazos_dias=7)

    item = correspondencias(http, cabecalho)[0]
    assert item["corresponde"] is True
    assert item["alerta_prazo"] is True


def test_prazo_proximo_nao_alerta_imovel_fora_dos_filtros(http, fabrica, cliente, autenticar):
    # Decisão 5 (28/10/2026): o alerta de prazo respeita os filtros do critério.
    fabrica.imovel(
        titulo="Fora do critério", estado="PR",
        data_primeiro_leilao=date.today() + timedelta(days=3),
    )
    cabecalho = autenticar(cliente)
    criar_alerta(http, cabecalho, estado="SP", alertar_prazos_dias=7)

    assert correspondencias(http, cabecalho) == []


# ---------------------------------------------------------- notificações

def nova_notificacao(sessao, usuario, imovel, evento="correspondencia", lida=False):
    notificacao = Notificacao(
        usuario_id=usuario.id,
        imovel_id=imovel.id,
        evento=evento,
        tipo="oportunidade",
        titulo="Nova oportunidade compatível",
        mensagem="Teste",
        lida=lida,
    )
    sessao.add(notificacao)
    sessao.commit()
    sessao.refresh(notificacao)
    return notificacao


def test_lista_e_conta_notificacoes_nao_lidas(http, sessao, fabrica, cliente, autenticar):
    imovel = fabrica.imovel()
    nova_notificacao(sessao, cliente, imovel, evento="a")
    nova_notificacao(sessao, cliente, imovel, evento="b", lida=True)
    cabecalho = autenticar(cliente)

    assert len(http.get("/alertas/notificacoes", headers=cabecalho).json()) == 2
    assert http.get("/alertas/notificacoes/nao-lidas", headers=cabecalho).json() == {"total": 1}


def test_marca_notificacao_como_lida(http, sessao, fabrica, cliente, autenticar):
    notificacao = nova_notificacao(sessao, cliente, fabrica.imovel())
    cabecalho = autenticar(cliente)

    resposta = http.post(f"/alertas/notificacoes/{notificacao.id}/lida", headers=cabecalho)
    assert resposta.status_code == 200 and resposta.json()["lida"] is True
    assert http.get("/alertas/notificacoes/nao-lidas", headers=cabecalho).json() == {"total": 0}


def test_notificacao_de_outra_pessoa_nao_e_acessivel(http, sessao, fabrica, cliente, outro_cliente, autenticar):
    notificacao = nova_notificacao(sessao, cliente, fabrica.imovel())
    intruso = autenticar(outro_cliente)

    assert http.get("/alertas/notificacoes", headers=intruso).json() == []
    assert http.post(f"/alertas/notificacoes/{notificacao.id}/lida", headers=intruso).status_code == 404
