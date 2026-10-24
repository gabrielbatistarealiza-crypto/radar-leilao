import pytest

from app.models.operacao import Operacao


@pytest.fixture()
def oportunidade(fabrica, cliente, corretor):
    return fabrica.oportunidade(cliente, fabrica.imovel(), corretor=corretor, status="em_contato")


def abrir_negociacao(http, cabecalho, oportunidade, **extra):
    corpo = {"oportunidade_id": oportunidade.id, **extra}
    return http.post("/negociacoes", json=corpo, headers=cabecalho)


def mudar_negociacao(http, cabecalho, negociacao_id, status, **extra):
    return http.patch(
        f"/negociacoes/{negociacao_id}/status",
        json={"status": status, **extra},
        headers=cabecalho,
    )


# ============================================================ negociações

def test_abrir_negociacao_coloca_a_oportunidade_em_negociando(
    http, sessao, oportunidade, cliente, autenticar
):
    resposta = abrir_negociacao(http, autenticar(cliente), oportunidade, valor_proposto=100000)
    assert resposta.status_code == 201
    assert resposta.json()["status"] == "aberta"
    sessao.refresh(oportunidade)
    assert oportunidade.status == "negociando"


def test_so_uma_negociacao_ativa_por_oportunidade(http, oportunidade, cliente, autenticar):
    cabecalho = autenticar(cliente)
    assert abrir_negociacao(http, cabecalho, oportunidade).status_code == 201
    assert abrir_negociacao(http, cabecalho, oportunidade).status_code == 409


def test_nao_negocia_oportunidade_encerrada(http, sessao, oportunidade, cliente, autenticar):
    oportunidade.status = "cancelada"
    sessao.commit()
    assert abrir_negociacao(http, autenticar(cliente), oportunidade).status_code == 400


def test_oportunidade_inexistente_retorna_404(http, cliente, autenticar):
    resposta = http.post(
        "/negociacoes", json={"oportunidade_id": 99999}, headers=autenticar(cliente)
    )
    assert resposta.status_code == 404


def test_quem_nao_participa_nao_abre_negociacao(http, oportunidade, outro_cliente, outro_corretor, autenticar):
    assert abrir_negociacao(http, autenticar(outro_cliente), oportunidade).status_code == 403
    assert abrir_negociacao(http, autenticar(outro_corretor), oportunidade).status_code == 403


def test_corretor_responsavel_e_admin_podem_negociar(http, fabrica, cliente, corretor, admin, autenticar):
    primeira = fabrica.oportunidade(cliente, fabrica.imovel(), corretor=corretor)
    segunda = fabrica.oportunidade(cliente, fabrica.imovel(), corretor=corretor)
    assert abrir_negociacao(http, autenticar(corretor), primeira).status_code == 201
    assert abrir_negociacao(http, autenticar(admin), segunda).status_code == 201


def test_contraproposta_exige_valor_positivo(http, fabrica, oportunidade, corretor, autenticar):
    negociacao = fabrica.negociacao(oportunidade)
    cabecalho = autenticar(corretor)
    assert mudar_negociacao(http, cabecalho, negociacao.id, "contraproposta").status_code == 400
    assert (
        mudar_negociacao(http, cabecalho, negociacao.id, "contraproposta", valor_proposto=0).status_code
        == 400
    )


def test_contraproposta_atualiza_valor_e_observacao(http, fabrica, oportunidade, corretor, autenticar):
    negociacao = fabrica.negociacao(oportunidade, valor=100000)
    resposta = mudar_negociacao(
        http, autenticar(corretor), negociacao.id, "contraproposta",
        valor_proposto=110000, observacoes="  Meu melhor valor  ",
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "contraproposta"
    assert corpo["valor_proposto"] == pytest.approx(110000)
    assert corpo["observacoes"] == "Meu melhor valor"


def test_aceitar_conclui_a_oportunidade(http, sessao, fabrica, oportunidade, corretor, autenticar):
    negociacao = fabrica.negociacao(oportunidade)
    resposta = mudar_negociacao(http, autenticar(corretor), negociacao.id, "aceita")
    assert resposta.status_code == 200
    sessao.refresh(oportunidade)
    assert oportunidade.status == "concluida"


@pytest.mark.parametrize("status", ["recusada", "cancelada"])
def test_recusar_ou_cancelar_volta_a_oportunidade_para_em_contato(
    http, sessao, fabrica, oportunidade, corretor, autenticar, status
):
    oportunidade.status = "negociando"
    sessao.commit()
    negociacao = fabrica.negociacao(oportunidade)
    assert mudar_negociacao(http, autenticar(corretor), negociacao.id, status).status_code == 200
    sessao.refresh(oportunidade)
    assert oportunidade.status == "em_contato"


def test_status_de_negociacao_invalido(http, fabrica, oportunidade, corretor, autenticar):
    negociacao = fabrica.negociacao(oportunidade)
    assert mudar_negociacao(http, autenticar(corretor), negociacao.id, "inventado").status_code == 400


def test_negociacao_inexistente_retorna_404(http, corretor, autenticar):
    assert mudar_negociacao(http, autenticar(corretor), 99999, "aceita").status_code == 404


def test_terceiro_nao_altera_negociacao(http, fabrica, oportunidade, outro_cliente, autenticar):
    negociacao = fabrica.negociacao(oportunidade)
    assert mudar_negociacao(http, autenticar(outro_cliente), negociacao.id, "aceita").status_code == 403


def test_lista_negociacoes_da_oportunidade_da_mais_nova_para_a_mais_antiga(
    http, fabrica, oportunidade, cliente, outro_cliente, autenticar
):
    antiga = fabrica.negociacao(oportunidade, status="recusada")
    nova = fabrica.negociacao(oportunidade, status="aberta")
    url = f"/negociacoes/oportunidade/{oportunidade.id}"

    resposta = http.get(url, headers=autenticar(cliente))
    assert resposta.status_code == 200
    assert [n["id"] for n in resposta.json()] == [nova.id, antiga.id]
    assert http.get(url, headers=autenticar(outro_cliente)).status_code == 403


@pytest.mark.xfail(
    reason="Decisão de negócio pendente: hoje qualquer transição é aceita, "
    "inclusive reabrir ou recusar uma negociação já aceita.",
    strict=False,
)
def test_negociacao_aceita_nao_deveria_voltar_para_recusada(
    http, fabrica, oportunidade, corretor, autenticar
):
    negociacao = fabrica.negociacao(oportunidade, status="aceita")
    resposta = mudar_negociacao(http, autenticar(corretor), negociacao.id, "recusada")
    assert resposta.status_code == 400


# ============================================================== operações

@pytest.fixture()
def venda_fechada(sessao, fabrica, cliente, corretor):
    """Oportunidade concluída, com negociação aceita."""
    oportunidade = fabrica.oportunidade(
        cliente, fabrica.imovel(), corretor=corretor, status="concluida"
    )
    fabrica.negociacao(oportunidade, status="aceita")
    return oportunidade


def criar_operacao(http, cabecalho, oportunidade, valor=100000):
    return http.post(
        "/operacoes",
        json={"oportunidade_id": oportunidade.id, "valor_imovel": valor},
        headers=cabecalho,
    )


def test_corretor_responsavel_cria_operacao_com_taxa_de_10_por_cento(
    http, venda_fechada, corretor, autenticar
):
    resposta = criar_operacao(http, autenticar(corretor), venda_fechada, valor=250000)
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["status"] == "em_andamento"
    assert corpo["percentual_taxa"] == pytest.approx(10)
    assert corpo["valor_taxa"] == pytest.approx(25000)
    assert corpo["concluido_em"] is None


def test_admin_tambem_cria_operacao(http, venda_fechada, admin, autenticar):
    assert criar_operacao(http, autenticar(admin), venda_fechada).status_code == 201


def test_cliente_e_outro_corretor_nao_criam_operacao(
    http, venda_fechada, cliente, outro_corretor, autenticar
):
    assert criar_operacao(http, autenticar(cliente), venda_fechada).status_code == 403
    assert criar_operacao(http, autenticar(outro_corretor), venda_fechada).status_code == 403


def test_operacao_exige_oportunidade_concluida(http, oportunidade, corretor, autenticar):
    resposta = criar_operacao(http, autenticar(corretor), oportunidade)
    assert resposta.status_code == 400


def test_operacao_exige_negociacao_aceita(http, sessao, fabrica, cliente, corretor, autenticar):
    concluida_sem_negociacao = fabrica.oportunidade(
        cliente, fabrica.imovel(), corretor=corretor, status="concluida"
    )
    resposta = criar_operacao(http, autenticar(corretor), concluida_sem_negociacao)
    assert resposta.status_code == 400
    assert sessao.query(Operacao).count() == 0


def test_nao_cria_duas_operacoes_para_a_mesma_oportunidade(
    http, venda_fechada, corretor, autenticar
):
    cabecalho = autenticar(corretor)
    assert criar_operacao(http, cabecalho, venda_fechada).status_code == 201
    assert criar_operacao(http, cabecalho, venda_fechada).status_code == 409


@pytest.mark.parametrize("valor", [0, -1])
def test_valor_do_imovel_precisa_ser_positivo(http, venda_fechada, corretor, autenticar, valor):
    assert criar_operacao(http, autenticar(corretor), venda_fechada, valor=valor).status_code == 400


def test_oportunidade_inexistente_na_operacao(http, corretor, autenticar):
    resposta = http.post(
        "/operacoes", json={"oportunidade_id": 99999, "valor_imovel": 1000},
        headers=autenticar(corretor),
    )
    assert resposta.status_code == 404


@pytest.fixture()
def operacao(http, venda_fechada, corretor, autenticar):
    resposta = criar_operacao(http, autenticar(corretor), venda_fechada)
    assert resposta.status_code == 201
    return resposta.json()


def mudar_operacao(http, cabecalho, operacao_id, status):
    return http.patch(
        f"/operacoes/{operacao_id}/status", json={"status": status}, headers=cabecalho
    )


def test_concluir_operacao_registra_a_data(http, operacao, corretor, autenticar):
    resposta = mudar_operacao(http, autenticar(corretor), operacao["id"], "concluida")
    assert resposta.status_code == 200
    assert resposta.json()["concluido_em"] is not None


@pytest.mark.parametrize("novo_status", ["em_andamento", "cancelada"])
def test_reabrir_ou_cancelar_limpa_a_data_de_conclusao(
    http, operacao, corretor, autenticar, novo_status
):
    cabecalho = autenticar(corretor)
    mudar_operacao(http, cabecalho, operacao["id"], "concluida")
    resposta = mudar_operacao(http, cabecalho, operacao["id"], novo_status)
    assert resposta.status_code == 200
    assert resposta.json()["concluido_em"] is None


def test_status_de_operacao_invalido(http, operacao, corretor, autenticar):
    assert mudar_operacao(http, autenticar(corretor), operacao["id"], "feita").status_code == 400


def test_cliente_nao_altera_operacao(http, operacao, cliente, autenticar):
    assert mudar_operacao(http, autenticar(cliente), operacao["id"], "concluida").status_code == 403


def test_operacao_inexistente_retorna_404(http, corretor, autenticar):
    assert mudar_operacao(http, autenticar(corretor), 99999, "concluida").status_code == 404


def test_cliente_da_oportunidade_consulta_a_operacao(http, venda_fechada, operacao, cliente, autenticar):
    resposta = http.get(f"/operacoes/oportunidade/{venda_fechada.id}", headers=autenticar(cliente))
    assert resposta.status_code == 200
    assert resposta.json()["id"] == operacao["id"]


def test_terceiro_nao_consulta_a_operacao(http, venda_fechada, operacao, outro_cliente, autenticar):
    resposta = http.get(
        f"/operacoes/oportunidade/{venda_fechada.id}", headers=autenticar(outro_cliente)
    )
    assert resposta.status_code == 403


def test_terceiro_nao_descobre_se_existe_operacao(http, oportunidade, outro_cliente, autenticar):
    # Antes da correção, quem não tinha acesso recebia 404 quando não existia
    # operação e 403 quando existia, o que revelava a existência dela.
    resposta = http.get(
        f"/operacoes/oportunidade/{oportunidade.id}", headers=autenticar(outro_cliente)
    )
    assert resposta.status_code == 403


def test_dono_ve_404_quando_ainda_nao_ha_operacao(http, oportunidade, cliente, autenticar):
    resposta = http.get(f"/operacoes/oportunidade/{oportunidade.id}", headers=autenticar(cliente))
    assert resposta.status_code == 404


def test_dashboard_inclui_negociacoes_e_operacoes(http, venda_fechada, operacao, cliente, autenticar):
    resposta = http.get(f"/oportunidades/cliente/{cliente.id}/dashboard", headers=autenticar(cliente))
    corpo = resposta.json()
    assert corpo["negociacoes"]["por_status"]["aceita"] == 1
    assert corpo["operacoes"]["por_status"]["em_andamento"] == 1
