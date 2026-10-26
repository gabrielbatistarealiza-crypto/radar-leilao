"""Limite de tentativas falhadas de login (decisão 4)."""
from conftest import SENHA, criar_usuario
from app.routers import login as modulo_login
from app.routers.login import LimiteTentativasLogin, TENTATIVAS_FALHADAS_MAX


def _falhar(http, email, vezes):
    return [
        http.post("/login", json={"email": email, "senha": "errada"}).status_code
        for _ in range(vezes)
    ]


def test_bloqueia_depois_do_maximo_de_falhas(http, cliente):
    assert _falhar(http, cliente.email, TENTATIVAS_FALHADAS_MAX) == [401] * TENTATIVAS_FALHADAS_MAX

    resposta = http.post("/login", json={"email": cliente.email, "senha": "errada"})

    assert resposta.status_code == 429
    assert int(resposta.headers["Retry-After"]) > 0


def test_bloqueio_tambem_recusa_a_senha_certa(http, cliente):
    _falhar(http, cliente.email, TENTATIVAS_FALHADAS_MAX)

    resposta = http.post("/login", json={"email": cliente.email, "senha": SENHA})

    assert resposta.status_code == 429


def test_bloqueio_nao_revela_se_o_email_existe(http, cliente):
    _falhar(http, cliente.email, TENTATIVAS_FALHADAS_MAX)
    _falhar(http, "ninguem@teste.com", TENTATIVAS_FALHADAS_MAX)

    existente = http.post("/login", json={"email": cliente.email, "senha": "errada"})
    inexistente = http.post("/login", json={"email": "ninguem@teste.com", "senha": "errada"})

    assert existente.status_code == inexistente.status_code == 429
    assert existente.json() == inexistente.json()


def test_bloqueio_e_por_email(http, cliente, outro_cliente):
    _falhar(http, cliente.email, TENTATIVAS_FALHADAS_MAX)

    resposta = http.post("/login", json={"email": outro_cliente.email, "senha": SENHA})

    assert resposta.status_code == 200


def test_email_com_maiusculas_conta_como_o_mesmo(http, cliente):
    _falhar(http, cliente.email.upper(), TENTATIVAS_FALHADAS_MAX)

    resposta = http.post("/login", json={"email": cliente.email, "senha": SENHA})

    assert resposta.status_code == 429


def test_login_certo_antes_do_maximo_limpa_as_falhas(http, cliente):
    _falhar(http, cliente.email, TENTATIVAS_FALHADAS_MAX - 1)
    assert http.post("/login", json={"email": cliente.email, "senha": SENHA}).status_code == 200

    assert _falhar(http, cliente.email, TENTATIVAS_FALHADAS_MAX - 1) == [401] * (TENTATIVAS_FALHADAS_MAX - 1)
    assert http.post("/login", json={"email": cliente.email, "senha": SENHA}).status_code == 200


def test_login_aceita_o_email_com_outras_maiusculas(http, cliente):
    resposta = http.post("/login", json={"email": cliente.email.upper(), "senha": SENHA})

    assert resposta.status_code == 200


def test_login_encontra_conta_guardada_com_maiusculas(http, sessao):
    criar_usuario(sessao, "Maria.Silva@teste.com")

    resposta = http.post("/login", json={"email": "maria.silva@teste.com", "senha": SENHA})

    assert resposta.status_code == 200


def test_contas_que_so_diferem_nas_maiusculas_so_entram_com_o_email_exato(http, sessao):
    criar_usuario(sessao, "Ana@teste.com")
    criar_usuario(sessao, "ana@teste.com")

    assert http.post("/login", json={"email": "Ana@teste.com", "senha": SENHA}).status_code == 200
    assert http.post("/login", json={"email": "ana@teste.com", "senha": SENHA}).status_code == 200
    assert http.post("/login", json={"email": "ANA@teste.com", "senha": SENHA}).status_code == 401


def test_bloqueio_expira_com_a_janela():
    agora = [1000.0]
    limite = LimiteTentativasLogin(maximo=2, janela=60, relogio=lambda: agora[0])
    limite.registar_falha("a@b.c")
    limite.registar_falha("a@b.c")
    assert limite.segundos_de_bloqueio("a@b.c") == 60

    agora[0] += 59
    assert limite.segundos_de_bloqueio("a@b.c") == 1

    agora[0] += 1
    assert limite.segundos_de_bloqueio("a@b.c") == 0


def test_cada_teste_comeca_sem_falhas(http, cliente):
    # O fixture http limpa o contador; sem isso, as falhas dos testes anteriores
    # (com o mesmo e-mail) bloqueariam este login.
    assert modulo_login.limite_login.segundos_de_bloqueio(cliente.email) == 0
    assert http.post("/login", json={"email": cliente.email, "senha": SENHA}).status_code == 200
