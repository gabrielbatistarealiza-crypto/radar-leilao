"""Registo público de clientes e pedidos de conta de corretor (aprovação pelo admin)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import database as banco
from app.models.corretor import Corretor
from app.models.pedido_corretor import PedidoCorretor
from app.models.usuario import Usuario
from app.routers import corretores, login, registo, usuarios


@pytest.fixture()
def api(sessao, monkeypatch):
    monkeypatch.delenv("RADAR_REGISTO_PUBLICO", raising=False)
    aplicacao = FastAPI()
    for modulo in (login, usuarios, corretores, registo):
        aplicacao.include_router(modulo.router)
    aplicacao.dependency_overrides[banco.get_db] = lambda: sessao
    aplicacao.dependency_overrides[corretores.get_db] = lambda: sessao
    login.limite_login.limpar_tudo()
    registo.limite_registo.limpar_tudo()
    return TestClient(aplicacao)


def registar(api, email="nova@teste.com", **extra):
    corpo = {"nome": "Nova Pessoa", "email": email, "senha": "segura123", **extra}
    return api.post("/registo", json=corpo)


def com_token(resposta):
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


DADOS_CORRETOR = {"creci": " creci-sp  12345-f ", "telefone": "11 99999-0000", "imobiliaria": "Imob X"}


# ---------------------------------------------------------------- registo

def test_registo_cria_cliente_e_devolve_token_valido(api, sessao):
    r = registar(api, email="Nova@Teste.com")

    assert r.status_code == 201
    corpo = r.json()
    assert corpo["usuario"]["tipo"] == "cliente" and corpo["usuario"]["admin"] is False
    assert corpo["usuario"]["email"] == "nova@teste.com"
    assert corpo["pedido_corretor"] is None
    eu = api.get("/usuarios/me", headers=com_token(r))
    assert eu.status_code == 200 and eu.json()["email"] == "nova@teste.com"
    # e consegue entrar com a senha escolhida
    assert api.post("/login", json={"email": "nova@teste.com", "senha": "segura123"}).status_code == 200


def test_registo_ignora_tipo_e_admin_enviados(api, sessao):
    r = registar(api, tipo="admin", admin=True)

    assert r.status_code == 201
    usuario = sessao.query(Usuario).one()
    assert usuario.tipo == "cliente" and usuario.admin is False


def test_email_repetido_mesmo_com_maiusculas_e_recusado(api, cliente):
    r = registar(api, email="CLIENTE@teste.com")
    assert r.status_code == 409


@pytest.mark.parametrize("campo, valor", [
    ("senha", "curta"), ("email", "nao-e-email"), ("nome", " "), ("senha", "x" * 129),
])
def test_dados_invalidos_sao_recusados(api, sessao, campo, valor):
    r = registar(api, **{campo: valor})
    assert r.status_code == 422
    assert sessao.query(Usuario).count() == 0


def test_registo_desligado_por_variavel(api, sessao, monkeypatch):
    monkeypatch.setenv("RADAR_REGISTO_PUBLICO", "0")
    assert registar(api).status_code == 403
    assert sessao.query(Usuario).count() == 0


def test_limite_de_registos_por_hora(api, monkeypatch):
    monkeypatch.setattr(registo.limite_registo, "maximo", 2)
    assert registar(api, email="a@teste.com").status_code == 201
    assert registar(api, email="b@teste.com").status_code == 201
    r = registar(api, email="c@teste.com")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


# ------------------------------------------------------ pedido de corretor

def test_registo_como_corretor_fica_cliente_com_pedido_pendente(api, sessao):
    r = registar(api, corretor=DADOS_CORRETOR)

    assert r.status_code == 201
    corpo = r.json()
    assert corpo["usuario"]["tipo"] == "cliente"
    assert corpo["pedido_corretor"]["status"] == "PENDENTE"
    assert corpo["pedido_corretor"]["creci"] == "CRECI-SP 12345-F"
    assert sessao.query(Corretor).count() == 0
    # Sem acesso de corretor antes da aprovação.
    usuario = sessao.query(Usuario).one()
    perfil = api.get(f"/corretores/usuario/{usuario.id}", headers=com_token(r))
    assert perfil.status_code == 403
    meu = api.get("/pedidos-corretor/meu", headers=com_token(r)).json()["pedido"]
    assert meu["status"] == "PENDENTE"


@pytest.mark.parametrize("creci", ["", "12", "SEM-NUMEROS", "<script>1</script>"])
def test_creci_invalido_nao_cria_conta(api, sessao, creci):
    r = registar(api, corretor={"creci": creci})
    assert r.status_code == 422
    assert sessao.query(Usuario).count() == 0


def test_creci_ja_usado_ou_pendente_e_recusado(api, sessao, fabrica, corretor):
    fabrica.perfil_corretor(corretor, creci="CRECI-SP 1")
    assert registar(api, email="a@teste.com", corretor={"creci": "crecI-sp 1"}).status_code == 409

    assert registar(api, email="b@teste.com", corretor={"creci": "CRECI-RJ 2"}).status_code == 201
    assert registar(api, email="c@teste.com", corretor={"creci": "creci-rj 2"}).status_code == 409
    assert sessao.query(Usuario).filter(Usuario.email.in_(["a@teste.com", "c@teste.com"])).count() == 0


def test_cliente_com_conta_pede_para_ser_corretor_uma_vez(api, cliente, autenticar):
    h = autenticar(cliente)
    assert api.post("/pedidos-corretor", json={"creci": "CRECI-MG 3"}, headers=h).status_code == 201
    assert api.post("/pedidos-corretor", json={"creci": "CRECI-MG 4"}, headers=h).status_code == 409


def test_corretor_e_admin_nao_podem_pedir(api, corretor, admin, autenticar):
    for usuario in (corretor, admin):
        r = api.post("/pedidos-corretor", json={"creci": "CRECI-MG 5"}, headers=autenticar(usuario))
        assert r.status_code == 400


def test_pedido_exige_login(api):
    assert api.post("/pedidos-corretor", json={"creci": "CRECI-MG 6"}).status_code == 401
    assert api.get("/pedidos-corretor/meu").status_code == 401


# ------------------------------------------------------------- aprovação

def pedido_de(api, email="futuro@teste.com"):
    r = registar(api, email=email, corretor=DADOS_CORRETOR)
    return r.json()["pedido_corretor"]["id"], com_token(r)


def test_so_admin_ve_e_decide_pedidos(api, cliente, corretor, autenticar):
    pedido_id, h_pedinte = pedido_de(api)
    for h in (h_pedinte, autenticar(cliente), autenticar(corretor)):
        assert api.get("/admin/pedidos-corretor", headers=h).status_code == 403
        assert api.post(f"/admin/pedidos-corretor/{pedido_id}/aprovar", headers=h).status_code == 403
        assert api.post(f"/admin/pedidos-corretor/{pedido_id}/rejeitar", json={}, headers=h).status_code == 403


def test_admin_lista_pendentes_com_oportunidades_do_cliente(api, sessao, admin, autenticar, fabrica):
    pedido_id, _ = pedido_de(api)
    usuario = sessao.query(Usuario).filter(Usuario.email == "futuro@teste.com").one()
    fabrica.oportunidade(usuario)

    lista = api.get("/admin/pedidos-corretor", headers=autenticar(admin)).json()

    assert [p["id"] for p in lista] == [pedido_id]
    assert lista[0]["usuario"]["email"] == "futuro@teste.com"
    assert lista[0]["oportunidades_como_cliente"] == 1
    assert api.get("/admin/pedidos-corretor?status=xpto", headers=autenticar(admin)).status_code == 400


def test_aprovar_cria_perfil_e_torna_corretor(api, sessao, admin, autenticar):
    pedido_id, h_pedinte = pedido_de(api)

    r = api.post(f"/admin/pedidos-corretor/{pedido_id}/aprovar", headers=autenticar(admin))

    assert r.status_code == 200 and r.json()["status"] == "APROVADO"
    sessao.expire_all()
    usuario = sessao.query(Usuario).filter(Usuario.email == "futuro@teste.com").one()
    assert usuario.tipo == "corretor" and usuario.admin is False
    perfil = sessao.query(Corretor).filter(Corretor.usuario_id == usuario.id).one()
    assert perfil.creci == "CRECI-SP 12345-F" and perfil.imobiliaria == "Imob X"
    pedido = sessao.get(PedidoCorretor, pedido_id)
    assert pedido.decidido_por == admin.id and pedido.decidido_em is not None
    # O mesmo token passa a ver o próprio perfil de corretor.
    assert api.get(f"/corretores/usuario/{usuario.id}", headers=h_pedinte).status_code == 200
    # Não se decide duas vezes.
    assert api.post(f"/admin/pedidos-corretor/{pedido_id}/aprovar", headers=autenticar(admin)).status_code == 409


def test_rejeitar_mantem_cliente_e_permite_novo_pedido(api, sessao, admin, autenticar):
    pedido_id, h_pedinte = pedido_de(api)

    r = api.post(f"/admin/pedidos-corretor/{pedido_id}/rejeitar",
                 json={"motivo": "  CRECI não encontrado  "}, headers=autenticar(admin))

    assert r.status_code == 200 and r.json()["status"] == "REJEITADO"
    assert r.json()["motivo"] == "CRECI não encontrado"
    sessao.expire_all()
    assert sessao.query(Usuario).filter(Usuario.email == "futuro@teste.com").one().tipo == "cliente"
    assert sessao.query(Corretor).count() == 0
    meu = api.get("/pedidos-corretor/meu", headers=h_pedinte).json()["pedido"]
    assert meu["status"] == "REJEITADO" and meu["motivo"] == "CRECI não encontrado"
    # O CRECI fica livre e pode voltar a pedir.
    assert api.post("/pedidos-corretor", json=DADOS_CORRETOR, headers=h_pedinte).status_code == 201


def test_aprovar_recusa_se_o_creci_entretanto_foi_usado(api, sessao, admin, corretor, autenticar, fabrica):
    pedido_id, _ = pedido_de(api)
    fabrica.perfil_corretor(corretor, creci="CRECI-SP 12345-F")

    r = api.post(f"/admin/pedidos-corretor/{pedido_id}/aprovar", headers=autenticar(admin))

    assert r.status_code == 409
    sessao.expire_all()
    assert sessao.get(PedidoCorretor, pedido_id).status == "PENDENTE"
    assert sessao.query(Usuario).filter(Usuario.email == "futuro@teste.com").one().tipo == "cliente"


def test_aprovar_pedido_inexistente(api, admin, autenticar):
    assert api.post("/admin/pedidos-corretor/999/aprovar", headers=autenticar(admin)).status_code == 404


def test_senha_guardada_com_hash(api, sessao):
    registar(api)
    assert sessao.query(Usuario).one().senha != "segura123"
