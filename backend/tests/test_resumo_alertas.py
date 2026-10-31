"""Resumo diário dos alertas por e-mail. O Brevo é trocado por um falso; sem rede."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.notificacao import Notificacao
from app.services import email as servico_email
from app.services import resumo_alertas as ra

MANHA = datetime(2026, 11, 2, 12, 0)  # depois das 11:00 UTC


class Caixa(list):
    """E-mails "enviados"; .estado["falhar"] simula o Brevo a recusar."""


@pytest.fixture()
def caixa_de_correio(monkeypatch):
    enviados = Caixa()
    estado = {"falhar": False}

    def enviar(para, assunto, html, texto):
        if estado["falhar"]:
            return False
        enviados.append(SimpleNamespace(para=para, assunto=assunto, html=html, texto=texto))
        return True

    monkeypatch.setattr(servico_email, "enviar_email", enviar)
    monkeypatch.setattr(servico_email, "email_configurado", lambda: True)
    monkeypatch.setenv("RADAR_SITE_URL", "https://site.exemplo")
    monkeypatch.delenv("RADAR_RESUMO_HORA_UTC", raising=False)
    enviados.estado = estado
    return enviados


def notificar(sessao, usuario, imovel, evento="correspondencia", criada_em=MANHA - timedelta(hours=2), tipo="oportunidade"):
    n = Notificacao(usuario_id=usuario.id, imovel_id=imovel.id, evento=evento, tipo=tipo,
                    titulo="Nova oportunidade compatível", mensagem=f"{imovel.titulo} corresponde.",
                    criada_em=criada_em)
    sessao.add(n)
    sessao.commit()
    return n


def test_envia_um_resumo_e_marca_as_notificacoes(sessao, fabrica, cliente, caixa_de_correio):
    a = fabrica.imovel(titulo="Casa A", valor_avaliacao=200000.0, valor_leilao=120000.0)
    notificar(sessao, cliente, a)

    r = ra.enviar_resumos(sessao, agora=MANHA)

    assert r["enviados"] == 1 and len(caixa_de_correio) == 1
    email = caixa_de_correio[0]
    assert email.para == cliente.email and "1 novidade" in email.assunto
    assert "Casa A" in email.texto and "40% abaixo da avaliação" in email.texto
    assert "https://site.exemplo/desligar-alertas?token=" in email.texto
    sessao.expire_all()
    assert sessao.query(Notificacao).one().enviada_por_email_em == MANHA
    assert cliente.ultimo_resumo_email_em == MANHA


def test_no_maximo_um_por_dia_e_volta_no_dia_seguinte(sessao, fabrica, cliente, caixa_de_correio):
    a, b = fabrica.imovel(titulo="A"), fabrica.imovel(titulo="B")
    notificar(sessao, cliente, a)
    ra.enviar_resumos(sessao, agora=MANHA)
    notificar(sessao, cliente, b, criada_em=MANHA + timedelta(hours=1))

    assert ra.enviar_resumos(sessao, agora=MANHA + timedelta(hours=3))["enviados"] == 0
    amanha = MANHA + timedelta(days=1)
    assert ra.enviar_resumos(sessao, agora=amanha)["enviados"] == 1
    assert len(caixa_de_correio) == 2 and "B" in caixa_de_correio[1].texto


def test_antes_da_hora_ou_sem_brevo_nao_envia(sessao, fabrica, cliente, caixa_de_correio, monkeypatch):
    notificar(sessao, cliente, fabrica.imovel())
    assert ra.enviar_resumos(sessao, agora=MANHA.replace(hour=9))["motivo"] == "ANTES_DA_HORA"
    monkeypatch.setattr(servico_email, "email_configurado", lambda: False)
    assert ra.enviar_resumos(sessao, agora=MANHA)["motivo"] == "EMAIL_NAO_CONFIGURADO"
    assert caixa_de_correio == []


def test_quem_desligou_nao_recebe(sessao, fabrica, cliente, caixa_de_correio):
    cliente.alertas_por_email = False
    sessao.commit()
    notificar(sessao, cliente, fabrica.imovel())
    assert ra.enviar_resumos(sessao, agora=MANHA)["enviados"] == 0 and caixa_de_correio == []


def test_falha_no_envio_tenta_outra_vez(sessao, fabrica, cliente, caixa_de_correio):
    notificar(sessao, cliente, fabrica.imovel())
    caixa_de_correio.estado["falhar"] = True
    assert ra.enviar_resumos(sessao, agora=MANHA)["falhados"] == 1
    caixa_de_correio.estado["falhar"] = False
    assert ra.enviar_resumos(sessao, agora=MANHA + timedelta(minutes=15))["enviados"] == 1


def test_mostra_dez_e_diz_quantos_faltam(sessao, fabrica, cliente, caixa_de_correio):
    for i in range(13):
        notificar(sessao, cliente, fabrica.imovel(titulo=f"Imóvel {i}"))
    ra.enviar_resumos(sessao, agora=MANHA)
    email = caixa_de_correio[0]
    assert "13 novidades" in email.assunto and "E mais 3 no site." in email.texto
    assert email.texto.count("\n- ") == 10
    sessao.expire_all()
    assert sessao.query(Notificacao).filter(Notificacao.enviada_por_email_em.is_(None)).count() == 0


def test_notificacoes_antigas_nao_seguem_por_email(sessao, fabrica, cliente, caixa_de_correio):
    notificar(sessao, cliente, fabrica.imovel(), criada_em=MANHA - timedelta(days=10))
    r = ra.enviar_resumos(sessao, agora=MANHA)
    assert r["enviados"] == 0 and caixa_de_correio == []
    sessao.expire_all()
    assert sessao.query(Notificacao).one().enviada_por_email_em == MANHA


def test_prazos_primeiro_e_depois_o_maior_desconto(sessao, fabrica, cliente, caixa_de_correio):
    pouco = fabrica.imovel(titulo="Pouco desconto", valor_avaliacao=100000.0, valor_leilao=90000.0, desconto=10.0)
    muito = fabrica.imovel(titulo="Muito desconto", valor_avaliacao=100000.0, valor_leilao=50000.0, desconto=50.0)
    prazo = fabrica.imovel(titulo="Com prazo", valor_avaliacao=100000.0, valor_leilao=95000.0, desconto=5.0)
    notificar(sessao, cliente, pouco)
    notificar(sessao, cliente, muito)
    n = notificar(sessao, cliente, prazo, evento="prazo:primeiro:2026-11-05", tipo="prazo")
    n.mensagem = "Com prazo: primeiro leilão em 3 dia(s), em 2026-11-05."
    sessao.commit()

    ra.enviar_resumos(sessao, agora=MANHA)

    linhas = [l for l in caixa_de_correio[0].texto.splitlines() if l.startswith("- ")]
    assert linhas[0].startswith("- Leilão a aproximar-se: Com prazo") and "primeiro leilão em 3 dia(s)" in linhas[0]
    assert "Muito desconto" in linhas[1] and "50% abaixo" in linhas[1]
    assert "Pouco desconto" in linhas[2]


def test_html_escapa_o_texto(sessao, fabrica, cliente, caixa_de_correio):
    notificar(sessao, cliente, fabrica.imovel(titulo="<script>x</script>"))
    ra.enviar_resumos(sessao, agora=MANHA)
    assert "<script>" not in caixa_de_correio[0].html


# -------------------------------------------------------- preferência e ligação

def test_ver_e_mudar_a_preferencia(http, cliente, autenticar):
    assert http.get("/alertas/email", headers=autenticar(cliente)).json()["ativo"] is True
    r = http.put("/alertas/email", json={"ativo": False}, headers=autenticar(cliente))
    assert r.status_code == 200 and r.json()["ativo"] is False
    assert http.get("/alertas/email", headers=autenticar(cliente)).json()["ativo"] is False
    assert http.get("/alertas/email").status_code == 401


def test_ligacao_do_email_desliga_sem_sessao(http, sessao, cliente):
    r = http.post("/alertas/email/desligar", json={"token": ra.token_desligar(cliente.id)})
    assert r.status_code == 200
    sessao.expire_all()
    assert cliente.alertas_por_email is False


def test_ligacao_invalida_e_recusada(http, cliente, autenticar):
    assert http.post("/alertas/email/desligar", json={"token": "x" * 40}).status_code == 400
    # Um token de sessão não serve para desligar...
    sessao_token = autenticar(cliente)["Authorization"].split()[1]
    assert http.post("/alertas/email/desligar", json={"token": sessao_token}).status_code == 400


def test_token_de_desligar_nao_serve_de_sessao(http, cliente):
    token = ra.token_desligar(cliente.id)
    assert http.get("/usuarios/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
