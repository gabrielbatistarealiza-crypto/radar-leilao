from conftest import SENHA
from app.models.usuario import Usuario


# ------------------------------------------------------------------- login

def test_login_com_credenciais_corretas(http, cliente):
    resposta = http.post("/login", json={"email": cliente.email, "senha": SENHA})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]


def test_login_com_senha_errada(http, cliente):
    resposta = http.post("/login", json={"email": cliente.email, "senha": "errada"})
    assert resposta.status_code == 401


def test_login_nao_revela_se_o_email_existe(http, cliente):
    senha_errada = http.post("/login", json={"email": cliente.email, "senha": "errada"})
    email_inexistente = http.post(
        "/login", json={"email": "ninguem@teste.com", "senha": SENHA}
    )
    assert email_inexistente.status_code == 401
    assert email_inexistente.json() == senha_errada.json()


def test_login_com_email_invalido_retorna_422(http):
    resposta = http.post("/login", json={"email": "nao-e-email", "senha": SENHA})
    assert resposta.status_code == 422


def test_senha_e_guardada_como_hash_bcrypt(sessao, cliente):
    sessao.refresh(cliente)
    assert cliente.senha != SENHA
    assert cliente.senha.startswith("$2")


# ----------------------------------------------------------------- /me

def test_me_devolve_o_usuario_sem_expor_a_senha(http, cliente, autenticar):
    resposta = http.get("/usuarios/me", headers=autenticar(cliente))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["email"] == cliente.email
    assert corpo["tipo"] == "cliente"
    assert "senha" not in corpo


def test_me_sem_token_retorna_401(http):
    assert http.get("/usuarios/me").status_code == 401


def test_me_com_token_invalido_retorna_401(http):
    resposta = http.get("/usuarios/me", headers={"Authorization": "Bearer lixo"})
    assert resposta.status_code == 401


def test_token_de_usuario_removido_deixa_de_valer(http, sessao, cliente, autenticar):
    cabecalho = autenticar(cliente)
    sessao.delete(cliente)
    sessao.commit()
    assert http.get("/usuarios/me", headers=cabecalho).status_code == 401


# ------------------------------------------------------- criar usuário

NOVO = {"nome": "Novo", "email": "novo@teste.com", "senha": "abc12345", "tipo": "corretor"}


def test_so_administrador_cria_usuario(http, cliente, corretor, autenticar):
    assert http.post("/usuarios", json=NOVO, headers=autenticar(cliente)).status_code == 403
    assert http.post("/usuarios", json=NOVO, headers=autenticar(corretor)).status_code == 403
    assert http.post("/usuarios", json=NOVO).status_code == 401


def test_admin_cria_usuario_com_tipo_e_senha_com_hash(http, sessao, admin, autenticar):
    resposta = http.post("/usuarios", json=NOVO, headers=autenticar(admin))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "corretor"
    assert corpo["admin"] is False
    assert "senha" not in corpo

    gravado = sessao.query(Usuario).filter(Usuario.email == NOVO["email"]).one()
    assert gravado.senha.startswith("$2")


def test_admin_cria_outro_admin(http, admin, autenticar):
    corpo = dict(NOVO, email="admin2@teste.com", tipo="admin")
    resposta = http.post("/usuarios", json=corpo, headers=autenticar(admin))
    assert resposta.status_code == 200
    assert resposta.json()["admin"] is True


def test_tipo_invalido_e_recusado(http, admin, autenticar):
    corpo = dict(NOVO, tipo="superusuario")
    resposta = http.post("/usuarios", json=corpo, headers=autenticar(admin))
    assert resposta.status_code == 400


def test_email_duplicado_e_recusado(http, admin, cliente, autenticar):
    corpo = dict(NOVO, email=cliente.email)
    resposta = http.post("/usuarios", json=corpo, headers=autenticar(admin))
    assert resposta.status_code == 400
