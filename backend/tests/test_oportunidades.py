import pytest

from app.models.atividade_oportunidade import AtividadeOportunidade


def criar(http, cabecalho, **corpo):
    return http.post("/oportunidades", json=corpo, headers=cabecalho)


# ------------------------------------------------------------ criação

def test_cliente_cria_oportunidade_para_si(http, fabrica, cliente, autenticar):
    imovel = fabrica.imovel(valor_avaliacao=250000.0)
    resposta = criar(http, autenticar(cliente), imovel_id=imovel.id, cliente_id=cliente.id)
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["status"] == "interesse"
    assert corpo["corretor_id"] is None
    assert corpo["valor_imovel"] == pytest.approx(250000.0)  # padrão: valor de avaliação


def test_cliente_nao_cria_para_outro_cliente(http, fabrica, cliente, outro_cliente, autenticar):
    imovel = fabrica.imovel()
    resposta = criar(http, autenticar(cliente), imovel_id=imovel.id, cliente_id=outro_cliente.id)
    assert resposta.status_code == 403


def test_cliente_nao_escolhe_corretor(http, fabrica, cliente, corretor, autenticar):
    imovel = fabrica.imovel()
    resposta = criar(
        http, autenticar(cliente),
        imovel_id=imovel.id, cliente_id=cliente.id, corretor_id=corretor.id,
    )
    assert resposta.status_code == 403


def test_exige_imovel_ou_anuncio_e_nunca_os_dois(http, fabrica, cliente, corretor, autenticar):
    imovel = fabrica.imovel()
    anuncio = fabrica.anuncio(fabrica.perfil_corretor(corretor))
    cabecalho = autenticar(cliente)
    assert criar(http, cabecalho, cliente_id=cliente.id).status_code == 400
    ambos = criar(
        http, cabecalho, imovel_id=imovel.id, anuncio_id=anuncio.id, cliente_id=cliente.id
    )
    assert ambos.status_code == 400


def test_imovel_inexistente_retorna_404(http, cliente, autenticar):
    resposta = criar(http, autenticar(cliente), imovel_id=99999, cliente_id=cliente.id)
    assert resposta.status_code == 404


def test_nao_permite_oportunidade_ativa_duplicada(http, fabrica, cliente, autenticar):
    imovel = fabrica.imovel()
    corpo = dict(imovel_id=imovel.id, cliente_id=cliente.id)
    assert criar(http, autenticar(cliente), **corpo).status_code == 201
    assert criar(http, autenticar(cliente), **corpo).status_code == 409


def test_pode_recriar_depois_de_cancelada(http, sessao, fabrica, cliente, autenticar):
    imovel = fabrica.imovel()
    antiga = fabrica.oportunidade(cliente, imovel, status="cancelada")
    assert antiga.id
    resposta = criar(http, autenticar(cliente), imovel_id=imovel.id, cliente_id=cliente.id)
    assert resposta.status_code == 201


def test_corretor_cria_para_cliente_ficando_como_responsavel(
    http, fabrica, cliente, corretor, autenticar
):
    imovel = fabrica.imovel()
    resposta = criar(http, autenticar(corretor), imovel_id=imovel.id, cliente_id=cliente.id)
    assert resposta.status_code == 201
    assert resposta.json()["corretor_id"] == corretor.id


def test_corretor_nao_atribui_a_outro_corretor(
    http, fabrica, cliente, corretor, outro_corretor, autenticar
):
    imovel = fabrica.imovel()
    resposta = criar(
        http, autenticar(corretor),
        imovel_id=imovel.id, cliente_id=cliente.id, corretor_id=outro_corretor.id,
    )
    assert resposta.status_code == 403


def test_corretor_so_cria_oportunidade_para_cliente(http, fabrica, corretor, admin, autenticar):
    imovel = fabrica.imovel()
    resposta = criar(http, autenticar(corretor), imovel_id=imovel.id, cliente_id=admin.id)
    assert resposta.status_code == 403


def test_sem_login_retorna_401(http, fabrica, cliente):
    imovel = fabrica.imovel()
    resposta = http.post("/oportunidades", json={"imovel_id": imovel.id, "cliente_id": cliente.id})
    assert resposta.status_code == 401


# ------------------------------------------------- anúncio de corretor

def test_interesse_em_anuncio_vai_para_o_corretor_dono(
    http, fabrica, cliente, corretor, autenticar
):
    anuncio = fabrica.anuncio(fabrica.perfil_corretor(corretor))
    resposta = criar(http, autenticar(cliente), anuncio_id=anuncio.id, cliente_id=cliente.id)
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["anuncio_id"] == anuncio.id
    assert corpo["imovel_id"] is None
    assert corpo["corretor_id"] == corretor.id
    assert corpo["valor_imovel"] == pytest.approx(70000.0)


def test_anuncio_nao_publicado_nao_recebe_interesse(
    http, fabrica, cliente, corretor, autenticar
):
    anuncio = fabrica.anuncio(fabrica.perfil_corretor(corretor), status="rascunho")
    resposta = criar(http, autenticar(cliente), anuncio_id=anuncio.id, cliente_id=cliente.id)
    assert resposta.status_code == 400


def test_rota_de_interesse_em_anuncio(http, fabrica, cliente, corretor, autenticar):
    # Antes da correção essa rota tratava o usuário como dict e dava erro 500.
    anuncio = fabrica.anuncio(fabrica.perfil_corretor(corretor))
    resposta = http.post(
        f"/oportunidades/anuncio/{anuncio.id}/interesse", headers=autenticar(cliente)
    )
    assert resposta.status_code == 201
    assert resposta.json()["cliente_id"] == cliente.id
    assert resposta.json()["corretor_id"] == corretor.id


def test_rota_de_interesse_nao_duplica_e_exige_cliente(
    http, fabrica, cliente, corretor, autenticar
):
    anuncio = fabrica.anuncio(fabrica.perfil_corretor(corretor))
    rota = f"/oportunidades/anuncio/{anuncio.id}/interesse"
    assert http.post(rota, headers=autenticar(cliente)).status_code == 201
    assert http.post(rota, headers=autenticar(cliente)).status_code == 409
    assert http.post(rota, headers=autenticar(corretor)).status_code == 403


# ----------------------------------------------------------- listagens

def test_cliente_lista_as_proprias_oportunidades(http, fabrica, cliente, autenticar):
    fabrica.oportunidade(cliente, fabrica.imovel())
    resposta = http.get(f"/oportunidades/cliente/{cliente.id}", headers=autenticar(cliente))
    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


def test_cliente_nao_lista_oportunidades_de_outro(http, cliente, outro_cliente, autenticar):
    resposta = http.get(
        f"/oportunidades/cliente/{outro_cliente.id}", headers=autenticar(cliente)
    )
    assert resposta.status_code == 403


def test_corretor_so_ve_oportunidades_atribuidas_a_ele(
    http, fabrica, cliente, corretor, outro_corretor, autenticar
):
    fabrica.oportunidade(cliente, fabrica.imovel(), corretor=outro_corretor)
    resposta = http.get(f"/oportunidades/cliente/{cliente.id}", headers=autenticar(corretor))
    assert resposta.status_code == 403


def test_corretor_lista_as_proprias_e_nao_as_de_outro(
    http, fabrica, cliente, corretor, outro_corretor, autenticar
):
    fabrica.oportunidade(cliente, fabrica.imovel(), corretor=corretor)
    propria = http.get(f"/oportunidades/corretor/{corretor.id}", headers=autenticar(corretor))
    assert propria.status_code == 200 and len(propria.json()) == 1
    alheia = http.get(
        f"/oportunidades/corretor/{outro_corretor.id}", headers=autenticar(corretor)
    )
    assert alheia.status_code == 403


def test_cliente_nao_ve_oportunidades_do_imovel_de_outros(
    http, fabrica, cliente, outro_cliente, autenticar
):
    imovel = fabrica.imovel()
    fabrica.oportunidade(outro_cliente, imovel)
    resposta = http.get(f"/oportunidades/imovel/{imovel.id}", headers=autenticar(cliente))
    assert resposta.status_code == 403


# -------------------------------------------------------------- status

@pytest.fixture()
def oportunidade(fabrica, cliente, corretor):
    return fabrica.oportunidade(cliente, fabrica.imovel(), corretor=corretor)


def mudar_status(http, cabecalho, oportunidade, status):
    return http.patch(
        f"/oportunidades/{oportunidade.id}/status", json={"status": status}, headers=cabecalho
    )


def test_corretor_responsavel_muda_status_e_gera_historico(
    http, sessao, oportunidade, corretor, autenticar
):
    resposta = mudar_status(http, autenticar(corretor), oportunidade, "em_contato")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "em_contato"

    atividade = sessao.query(AtividadeOportunidade).one()
    assert atividade.status_anterior == "interesse"
    assert atividade.status_novo == "em_contato"
    assert atividade.criado_por_id == corretor.id


def test_repetir_o_mesmo_status_nao_gera_historico(
    http, sessao, oportunidade, corretor, autenticar
):
    mudar_status(http, autenticar(corretor), oportunidade, "interesse")
    assert sessao.query(AtividadeOportunidade).count() == 0


def test_cliente_nao_muda_status(http, oportunidade, cliente, autenticar):
    assert mudar_status(http, autenticar(cliente), oportunidade, "cancelada").status_code == 403


def test_corretor_nao_responsavel_nao_muda_status(
    http, oportunidade, outro_corretor, autenticar
):
    resposta = mudar_status(http, autenticar(outro_corretor), oportunidade, "cancelada")
    assert resposta.status_code == 403


def test_admin_muda_status(http, oportunidade, admin, autenticar):
    assert mudar_status(http, autenticar(admin), oportunidade, "cancelada").status_code == 200


def test_status_invalido_e_recusado(http, oportunidade, corretor, autenticar):
    assert mudar_status(http, autenticar(corretor), oportunidade, "inventado").status_code == 400


# ----------------------------------------------------------- atividades

def test_corretor_registra_nota_e_contato(http, oportunidade, corretor, autenticar):
    url = f"/oportunidades/{oportunidade.id}/atividades"
    cabecalho = autenticar(corretor)

    nota = http.post(url, json={"tipo": "nota", "descricao": "Cliente quer visitar."}, headers=cabecalho)
    assert nota.status_code == 201 and nota.json()["canal"] is None

    contato = http.post(
        url, json={"tipo": "contato", "canal": "WhatsApp", "descricao": "Liguei."}, headers=cabecalho
    )
    assert contato.status_code == 201 and contato.json()["canal"] == "whatsapp"

    assert len(http.get(url, headers=cabecalho).json()) == 2


@pytest.mark.parametrize(
    "corpo",
    [
        {"tipo": "contato", "descricao": "sem canal"},
        {"tipo": "contato", "canal": "pombo", "descricao": "canal inválido"},
        {"tipo": "nota", "descricao": "   "},
        {"tipo": "outro", "descricao": "tipo inválido"},
        {"tipo": "nota", "descricao": "x" * 5001},
    ],
)
def test_atividade_invalida_retorna_400(http, oportunidade, corretor, autenticar, corpo):
    resposta = http.post(
        f"/oportunidades/{oportunidade.id}/atividades", json=corpo, headers=autenticar(corretor)
    )
    assert resposta.status_code == 400


def test_cliente_nao_acessa_o_historico(http, oportunidade, cliente, autenticar):
    url = f"/oportunidades/{oportunidade.id}/atividades"
    assert http.get(url, headers=autenticar(cliente)).status_code == 403
    corpo = {"tipo": "nota", "descricao": "oi"}
    assert http.post(url, json=corpo, headers=autenticar(cliente)).status_code == 403


# ------------------------------------------------------------ dashboard

def test_dashboard_do_cliente_conta_por_status(http, fabrica, cliente, autenticar):
    fabrica.oportunidade(cliente, fabrica.imovel(), status="interesse")
    fabrica.oportunidade(cliente, fabrica.imovel(), status="cancelada")
    resposta = http.get(
        f"/oportunidades/cliente/{cliente.id}/dashboard", headers=autenticar(cliente)
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["oportunidades"]["total"] == 2
    assert corpo["oportunidades"]["por_status"]["interesse"] == 1
    assert corpo["oportunidades"]["por_status"]["cancelada"] == 1
    assert corpo["negociacoes"]["total"] == 0
    assert corpo["operacoes"]["total"] == 0


def test_dashboard_de_outro_cliente_e_negado(http, cliente, outro_cliente, autenticar):
    resposta = http.get(
        f"/oportunidades/cliente/{outro_cliente.id}/dashboard", headers=autenticar(cliente)
    )
    assert resposta.status_code == 403


def test_dashboard_do_corretor(http, fabrica, cliente, corretor, outro_corretor, autenticar):
    fabrica.oportunidade(cliente, fabrica.imovel(), corretor=corretor)
    cabecalho = autenticar(corretor)
    propria = http.get(f"/oportunidades/corretor/{corretor.id}/dashboard", headers=cabecalho)
    assert propria.status_code == 200
    assert propria.json()["oportunidades"]["total"] == 1
    alheia = http.get(f"/oportunidades/corretor/{outro_corretor.id}/dashboard", headers=cabecalho)
    assert alheia.status_code == 403
