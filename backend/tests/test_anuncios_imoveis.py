"""Regressão das correções em app/routers/anuncios_imoveis.py.

Usa SQLite em memória e substitui o login, então não toca no Postgres.
Rodar a partir da pasta backend: pytest tests/test_anuncios_imoveis.py
"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registra todos os modelos antes do create_all)
from app.database.database import Base
from app.models.anuncio_imagem import AnuncioImagem
from app.models.anuncio_imovel import AnuncioImovel
from app.models.corretor import Corretor
from app.models.usuario import Usuario
from app.routers import anuncios_imoveis
from app.security.auth import usuario_atual, usuario_opcional


@pytest.fixture()
def sessao():
    motor = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(motor)
    Sessao = sessionmaker(bind=motor, autoflush=False, autocommit=False)
    db = Sessao()
    try:
        yield db
    finally:
        db.close()
        motor.dispose()


@pytest.fixture()
def dados(sessao):
    """Um corretor com um anúncio publicado (id 1) e um rascunho com foto (id 2)."""
    usuario = Usuario(nome="Corretor", email="c@teste.com", senha="x", tipo="corretor")
    sessao.add(usuario)
    sessao.flush()
    corretor = Corretor(usuario_id=usuario.id, creci="CRECI-1")
    sessao.add(corretor)
    sessao.flush()

    def anuncio(titulo, status):
        return AnuncioImovel(
            corretor_id=corretor.id,
            titulo=titulo,
            valor_mercado=100000,
            valor_anunciado=70000,
            desconto=30,
            status=status,
            ativo=True,
        )

    publicado = anuncio("Publicado", "publicado")
    rascunho = anuncio("Rascunho", "rascunho")
    sessao.add_all([publicado, rascunho])
    sessao.flush()
    sessao.add(AnuncioImagem(anuncio_id=publicado.id, url="http://x/pub.jpg", ordem=0))
    sessao.add(AnuncioImagem(anuncio_id=rascunho.id, url="http://x/secreta.jpg", ordem=0))
    sessao.commit()
    return SimpleNamespace(
        usuario=usuario, corretor=corretor, publicado=publicado, rascunho=rascunho
    )


def montar_cliente(sessao, usuario=None):
    app = FastAPI()
    app.include_router(anuncios_imoveis.router)
    app.dependency_overrides[anuncios_imoveis.get_db] = lambda: sessao
    app.dependency_overrides[usuario_opcional] = lambda: usuario
    app.dependency_overrides[usuario_atual] = lambda: usuario
    return TestClient(app)


def corpo_atualizacao(corretor_id, mercado=100000, anunciado=70000):
    return {
        "corretor_id": corretor_id,
        "titulo": "Editado",
        "valor_mercado": mercado,
        "valor_anunciado": anunciado,
    }


def dono(dados):
    return SimpleNamespace(id=dados.usuario.id, tipo="corretor", admin=False)


# ---------- fotos ----------

def test_visitante_ve_fotos_de_anuncio_publicado(sessao, dados):
    http = montar_cliente(sessao, None)
    resposta = http.get(f"/anuncios-imoveis/{dados.publicado.id}/fotos")
    assert resposta.status_code == 200
    assert [f["url"] for f in resposta.json()] == ["http://x/pub.jpg"]


def test_visitante_nao_ve_fotos_de_rascunho_mesmo_com_outro_anuncio_publicado(sessao, dados):
    # Antes da correção, a checagem olhava o primeiro anúncio do corretor
    # (o publicado) e liberava as fotos do rascunho.
    http = montar_cliente(sessao, None)
    resposta = http.get(f"/anuncios-imoveis/{dados.rascunho.id}/fotos")
    assert resposta.status_code == 404
    assert "secreta" not in resposta.text


def test_visitante_nao_ve_fotos_de_anuncio_inativo(sessao, dados):
    dados.publicado.ativo = False
    sessao.commit()
    http = montar_cliente(sessao, None)
    resposta = http.get(f"/anuncios-imoveis/{dados.publicado.id}/fotos")
    assert resposta.status_code == 404


def test_dono_ve_fotos_do_proprio_rascunho(sessao, dados):
    http = montar_cliente(sessao, dono(dados))
    resposta = http.get(f"/anuncios-imoveis/{dados.rascunho.id}/fotos")
    assert resposta.status_code == 200
    assert resposta.json()[0]["url"] == "http://x/secreta.jpg"


# ---------- listagem pública ----------

def test_publicados_lista_so_publicados_com_fotos(sessao, dados):
    http = montar_cliente(sessao, None)
    resposta = http.get("/anuncios-imoveis/publicados")
    assert resposta.status_code == 200
    itens = resposta.json()
    assert [i["titulo"] for i in itens] == ["Publicado"]
    assert itens[0]["fotos"][0]["url"] == "http://x/pub.jpg"


# ---------- atualização ----------

def test_atualizar_com_desconto_valido(sessao, dados):
    http = montar_cliente(sessao, dono(dados))
    resposta = http.put(
        f"/anuncios-imoveis/{dados.publicado.id}",
        json=corpo_atualizacao(dados.corretor.id, mercado=100000, anunciado=75000),
    )
    assert resposta.status_code == 200
    assert resposta.json()["desconto"] == pytest.approx(25.0)


def test_atualizar_com_desconto_abaixo_do_minimo_e_recusado(sessao, dados):
    http = montar_cliente(sessao, dono(dados))
    resposta = http.put(
        f"/anuncios-imoveis/{dados.publicado.id}",
        json=corpo_atualizacao(dados.corretor.id, mercado=100000, anunciado=90000),
    )
    assert resposta.status_code == 400
    assert "20%" in resposta.json()["detail"]
    sessao.refresh(dados.publicado)
    assert dados.publicado.valor_anunciado == 70000  # nada foi gravado


def test_atualizar_com_valor_anunciado_maior_que_o_de_mercado_e_recusado(sessao, dados):
    http = montar_cliente(sessao, dono(dados))
    resposta = http.put(
        f"/anuncios-imoveis/{dados.publicado.id}",
        json=corpo_atualizacao(dados.corretor.id, mercado=100000, anunciado=120000),
    )
    assert resposta.status_code == 400


def test_outro_corretor_nao_atualiza_anuncio_alheio(sessao, dados):
    intruso = SimpleNamespace(id=dados.usuario.id + 99, tipo="corretor", admin=False)
    http = montar_cliente(sessao, intruso)
    resposta = http.put(
        f"/anuncios-imoveis/{dados.publicado.id}",
        json=corpo_atualizacao(dados.corretor.id),
    )
    assert resposta.status_code == 403
