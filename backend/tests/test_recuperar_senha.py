"""Fase 4B: recuperação de senha por e-mail (Brevo trocado por um falso). Sem rede."""
import re
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import database as banco
from app.models.recuperacao_senha import RecuperacaoSenha
from app.routers import login, senha
from app.services import email as servico_email


@pytest.fixture()
def api(sessao, monkeypatch):
    enviados = []

    def enviar_falso(para, assunto, html, texto):
        enviados.append(SimpleNamespace(para=para, assunto=assunto, html=html, texto=texto))
        return True

    monkeypatch.setattr(servico_email, "enviar_email", enviar_falso)
    monkeypatch.setenv("RADAR_SITE_URL", "https://site.exemplo/")
    senha.limite_por_email.limpar_tudo()
    senha.limite_global.limpar_tudo()
    login.limite_login.limpar_tudo()
    app = FastAPI()
    app.include_router(senha.router)
    app.include_router(login.router)
    app.dependency_overrides[banco.get_db] = lambda: sessao
    cliente_http = TestClient(app)
    cliente_http.enviados = enviados
    return cliente_http


def codigo_do_email(mensagem):
    return re.search(r"codigo=([\w-]+)", mensagem.texto).group(1)


RESPOSTA = "Se o e-mail estiver registado, enviámos uma ligação para redefinir a senha."


def test_pedido_envia_ligacao_e_redefinir_troca_a_senha(api, cliente):
    r = api.post("/senha/esquecida", json={"email": "CLIENTE@teste.com"})
    assert r.status_code == 200 and r.json()["mensagem"] == RESPOSTA
    assert len(api.enviados) == 1 and api.enviados[0].para == "cliente@teste.com"
    assert "https://site.exemplo/redefinir-senha?codigo=" in api.enviados[0].texto

    codigo = codigo_do_email(api.enviados[0])
    r = api.post("/senha/redefinir", json={"codigo": codigo, "senha": "novaSenha123"})
    assert r.status_code == 200

    assert api.post("/login", json={"email": "cliente@teste.com", "senha": "novaSenha123"}).status_code == 200
    assert api.post("/login", json={"email": "cliente@teste.com", "senha": "Senha#12345"}).status_code == 401


def test_email_desconhecido_tem_a_mesma_resposta_e_nao_envia(api, sessao):
    r = api.post("/senha/esquecida", json={"email": "ninguem@teste.com"})
    assert r.status_code == 200 and r.json()["mensagem"] == RESPOSTA
    assert api.enviados == [] and sessao.query(RecuperacaoSenha).count() == 0


def test_so_o_hash_do_codigo_fica_na_base(api, sessao, cliente):
    api.post("/senha/esquecida", json={"email": cliente.email})
    codigo = codigo_do_email(api.enviados[0])
    guardado = sessao.query(RecuperacaoSenha).one()
    assert codigo not in guardado.codigo_hash and len(guardado.codigo_hash) == 64


def test_ligacao_so_serve_uma_vez(api, cliente):
    api.post("/senha/esquecida", json={"email": cliente.email})
    codigo = codigo_do_email(api.enviados[0])
    assert api.post("/senha/redefinir", json={"codigo": codigo, "senha": "primeira123"}).status_code == 200
    r = api.post("/senha/redefinir", json={"codigo": codigo, "senha": "segunda123"})
    assert r.status_code == 400 and "inválida ou expirada" in r.json()["detail"]


def test_ligacao_expirada_e_recusada(api, sessao, cliente):
    api.post("/senha/esquecida", json={"email": cliente.email})
    codigo = codigo_do_email(api.enviados[0])
    pedido = sessao.query(RecuperacaoSenha).one()
    pedido.expira_em = datetime.utcnow() - timedelta(minutes=1)
    sessao.commit()
    assert api.post("/senha/redefinir", json={"codigo": codigo, "senha": "novaSenha123"}).status_code == 400


def test_redefinir_invalida_as_outras_ligacoes_pendentes(api, cliente):
    api.post("/senha/esquecida", json={"email": cliente.email})
    api.post("/senha/esquecida", json={"email": cliente.email})
    primeiro, segundo = (codigo_do_email(m) for m in api.enviados)
    assert api.post("/senha/redefinir", json={"codigo": segundo, "senha": "novaSenha123"}).status_code == 200
    assert api.post("/senha/redefinir", json={"codigo": primeiro, "senha": "outra12345"}).status_code == 400


def test_codigo_inventado_e_senha_curta(api):
    assert api.post("/senha/redefinir", json={"codigo": "x" * 43, "senha": "novaSenha123"}).status_code == 400
    assert api.post("/senha/redefinir", json={"codigo": "x" * 43, "senha": "curta"}).status_code == 422


def test_limite_de_pedidos_por_email(api, cliente):
    for _ in range(5):
        r = api.post("/senha/esquecida", json={"email": cliente.email})
        assert r.status_code == 200 and r.json()["mensagem"] == RESPOSTA
    assert len(api.enviados) == 3  # o resto é ignorado em silêncio


def test_envio_sem_configuracao_nao_falha(monkeypatch):
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    assert servico_email.enviar_email("a@b.com", "x", "<p>x</p>", "x") is False


def test_envio_pelo_brevo_com_a_chave_e_o_remetente(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "chave-falsa")
    monkeypatch.setenv("RADAR_EMAIL_REMETENTE", "naoresponder@exemplo.com")
    chamadas = []

    def post_falso(url, json, headers, timeout):
        chamadas.append((url, json, headers))
        return SimpleNamespace(status_code=201)

    assert servico_email.enviar_email("a@b.com", "Assunto", "<p>Olá</p>", "Olá", enviar=post_falso) is True
    url, corpo, cabecalhos = chamadas[0]
    assert url == servico_email.URL_BREVO and cabecalhos["api-key"] == "chave-falsa"
    assert corpo["sender"]["email"] == "naoresponder@exemplo.com" and corpo["to"] == [{"email": "a@b.com"}]

    falha = lambda *a, **k: SimpleNamespace(status_code=401)  # noqa: E731
    assert servico_email.enviar_email("a@b.com", "x", "x", "x", enviar=falha) is False
