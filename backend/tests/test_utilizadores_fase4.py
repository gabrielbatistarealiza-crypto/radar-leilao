"""Fase 4: papel só no tipo e token pelo id. Sem rede."""
from alembic import command
from sqlalchemy import text

from app import migrar
from app.models.usuario import Usuario
from app.security.token import criar_token, token_do_usuario


def cabecalho(token):
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------- papel no tipo

def test_admin_e_derivado_do_tipo(sessao):
    u = Usuario(nome="A", email="a@teste.com", senha="x", tipo="cliente")
    sessao.add(u)
    sessao.commit()
    assert u.admin is False

    u.admin = True
    sessao.commit()
    assert u.tipo == "admin"

    u.tipo = "corretor"
    sessao.commit()
    assert u.admin is False


def test_coluna_antiga_admin_nao_e_lida_nem_escrita(sessao, motor):
    # Passo A da remoção: com esta versão no ar a migração pode apagar a coluna.
    import re

    from sqlalchemy import event

    comandos = []

    def guardar(conn, cursor, sql, *resto):
        comandos.append(sql)

    event.listen(motor, "before_cursor_execute", guardar)
    try:
        sessao.add(Usuario(nome="A", email="a@teste.com", senha="x", tipo="admin"))
        sessao.commit()
        sessao.expire_all()
        assert sessao.query(Usuario).filter(Usuario.admin.is_(True)).one().email == "a@teste.com"
    finally:
        event.remove(motor, "before_cursor_execute", guardar)
    sql = [c for c in comandos if "usuarios" in c]
    # "admin" como coluna: "usuarios.admin" ou "(…, admin, …)" no INSERT.
    assert sql and not any(re.search(r"usuarios\.admin\b|[(,]\s*admin\b", c) for c in sql), sql


def test_desligar_admin_volta_a_cliente(sessao):
    u = Usuario(nome="A", email="a@teste.com", senha="x", tipo="admin")
    u.admin = False
    assert u.tipo == "cliente"


def test_consulta_por_admin_usa_o_tipo(sessao):
    sessao.add_all([
        Usuario(nome="A", email="a@teste.com", senha="x", tipo="admin"),
        Usuario(nome="B", email="b@teste.com", senha="x", tipo="cliente"),
    ])
    sessao.commit()
    assert [u.email for u in sessao.query(Usuario).filter(Usuario.admin.is_(True))] == ["a@teste.com"]


def test_api_continua_a_devolver_admin(http, admin, cliente, autenticar):
    assert http.get("/usuarios/me", headers=autenticar(admin)).json()["admin"] is True
    corpo = http.get("/usuarios/me", headers=autenticar(cliente)).json()
    assert corpo["admin"] is False and corpo["tipo"] == "cliente"


# ---------------------------------------------------------------- token

def test_token_novo_identifica_pelo_id(http, cliente):
    r = http.get("/usuarios/me", headers=cabecalho(token_do_usuario(cliente)))
    assert r.status_code == 200 and r.json()["email"] == cliente.email


def test_mudar_o_email_nao_termina_a_sessao(http, sessao, cliente):
    token = token_do_usuario(cliente)
    cliente.email = "novo.email@teste.com"
    sessao.commit()

    r = http.get("/usuarios/me", headers=cabecalho(token))

    assert r.status_code == 200 and r.json()["email"] == "novo.email@teste.com"


def test_tokens_antigos_continuam_validos(http, cliente):
    # Emitidos antes da fase 4: e-mail em "sub" e o id em "id".
    antigo = criar_token({"sub": cliente.email, "id": cliente.id})
    assert http.get("/usuarios/me", headers=cabecalho(antigo)).status_code == 200
    # Muito antigos: só o e-mail.
    so_email = criar_token({"sub": cliente.email})
    assert http.get("/usuarios/me", headers=cabecalho(so_email)).status_code == 200


def test_token_de_utilizador_apagado_e_recusado(http, sessao, cliente):
    token = token_do_usuario(cliente)
    sessao.delete(cliente)
    sessao.commit()
    assert http.get("/usuarios/me", headers=cabecalho(token)).status_code == 401


def test_login_devolve_token_pelo_id(http, cliente):
    from jose import jwt

    from app.security.token import ALGORITHM, SECRET_KEY

    r = http.post("/login", json={"email": cliente.email, "senha": "Senha#12345"})  # SENHA do conftest
    assert r.status_code == 200, r.text
    dados = jwt.decode(r.json()["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert dados["sub"] == str(cliente.id) and dados["id"] == cliente.id


# ------------------------------------------------------------- migração 0004

def test_migracao_0004_acerta_tipo_e_coluna_antiga(motor):
    from app.database.database import Base

    Base.metadata.drop_all(motor)
    with motor.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS alembic_version"))
    try:
        with motor.begin() as c:
            command.upgrade(migrar.configuracao(c), "0003")
            c.execute(text(
                "INSERT INTO usuarios (nome, email, senha, admin, tipo) VALUES "
                "('A', 'a@t.com', 'x', true, 'cliente'), "   # admin pela coluna antiga
                "('B', 'b@t.com', 'x', false, 'admin'), "    # admin pelo tipo
                "('C', 'c@t.com', 'x', false, 'corretor')"))
        with motor.begin() as c:
            command.upgrade(migrar.configuracao(c), "0004")
        with motor.connect() as c:
            linhas = c.execute(text("SELECT email, tipo, admin FROM usuarios ORDER BY email")).all()
        assert [(e, t, bool(a)) for e, t, a in linhas] == [
            ("a@t.com", "admin", True), ("b@t.com", "admin", True), ("c@t.com", "corretor", False)]
    finally:
        Base.metadata.drop_all(motor)
        with motor.begin() as c:
            c.execute(text("DROP TABLE IF EXISTS alembic_version"))
