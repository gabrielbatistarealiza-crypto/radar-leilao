"""Base comum dos testes de API do Radar Leilão.

Como rodar (a partir da pasta backend):
    pip install pytest httpx
    pytest

Por padrão usa SQLite em memória: rápido e sem tocar no seu Postgres.
Alguns testes (filtro de cidade sem acento, ordenação por score) dependem de
funções do PostgreSQL e são PULADOS no SQLite. Para rodá-los, aponte para um
banco de teste (o nome do banco PRECISA conter "test"; as tabelas são apagadas):
    set TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/arremata_test
"""
import os
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registra os modelos)
from app.database import database as banco
from app.database.database import Base
from app.models.anuncio_imagem import AnuncioImagem
from app.models.anuncio_imovel import AnuncioImovel
from app.models.corretor import Corretor
from app.models.imovel import Imovel, ImovelImagem
from app.models.negociacao import Negociacao
from app.models.notificacao import Notificacao  # noqa: F401
from app.models.oportunidade import Oportunidade
from app.models.simulacao_rentabilidade import SimulacaoRentabilidade  # noqa: F401
from app.models.usuario import Usuario
from app.routers import (
    alertas,
    anuncios_imoveis,
    imoveis,
    login,
    negociacoes,
    operacoes,
    oportunidades,
    simulacoes_rentabilidade,
    usuarios,
)
from app.security.password import gerar_hash
from app.security.token import criar_token

SENHA = "Senha#12345"
_HASH = gerar_hash(SENHA)  # bcrypt é lento: calcula uma vez só

ROUTERS = (
    login,
    usuarios,
    imoveis,
    oportunidades,
    negociacoes,
    operacoes,
    simulacoes_rentabilidade,
    anuncios_imoveis,
    alertas,
)


@pytest.fixture()
def motor():
    url = os.getenv("TEST_DATABASE_URL", "sqlite://")
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        nome_do_banco = url.rsplit("/", 1)[-1]
        if "test" not in nome_do_banco:
            pytest.exit(
                "TEST_DATABASE_URL deve apontar para um banco cujo nome contenha 'test'.",
                returncode=2,
            )
        engine = create_engine(url)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def sessao(motor):
    fabrica = sessionmaker(bind=motor, autoflush=False, autocommit=False)
    db = fabrica()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def eh_postgres(motor):
    return motor.dialect.name == "postgresql"


@pytest.fixture()
def http(sessao):
    """Cliente HTTP com os routers reais e o banco de teste.

    Vários routers definem o próprio get_db, então cada um é substituído.
    O login é o de verdade: o token é validado por app.security.auth.
    """
    aplicacao = FastAPI()
    for modulo in ROUTERS:
        aplicacao.include_router(modulo.router)

    # O limite de tentativas de login vive no módulo: cada teste começa do zero.
    login.limite_login.limpar_tudo()

    def usar_sessao():
        return sessao

    aplicacao.dependency_overrides[banco.get_db] = usar_sessao
    for modulo in ROUTERS:
        if hasattr(modulo, "get_db"):
            aplicacao.dependency_overrides[modulo.get_db] = usar_sessao

    return TestClient(aplicacao)


# ---------------------------------------------------------------- usuários

def criar_usuario(sessao, email, tipo="cliente"):
    usuario = Usuario(
        nome=email.split("@")[0],
        email=email,
        senha=_HASH,
        tipo=tipo,
        admin=(tipo == "admin"),
    )
    sessao.add(usuario)
    sessao.commit()
    sessao.refresh(usuario)
    return usuario


@pytest.fixture()
def cliente(sessao):
    return criar_usuario(sessao, "cliente@teste.com", "cliente")


@pytest.fixture()
def outro_cliente(sessao):
    return criar_usuario(sessao, "outro.cliente@teste.com", "cliente")


@pytest.fixture()
def corretor(sessao):
    return criar_usuario(sessao, "corretor@teste.com", "corretor")


@pytest.fixture()
def outro_corretor(sessao):
    return criar_usuario(sessao, "outro.corretor@teste.com", "corretor")


@pytest.fixture()
def admin(sessao):
    return criar_usuario(sessao, "admin@teste.com", "admin")


@pytest.fixture()
def autenticar():
    def _autenticar(usuario):
        token = criar_token({"sub": usuario.email, "id": usuario.id})
        return {"Authorization": f"Bearer {token}"}

    return _autenticar


# ------------------------------------------------------------------ fábricas

class Fabrica:
    def __init__(self, sessao):
        self.sessao = sessao

    def _salvar(self, objeto):
        self.sessao.add(objeto)
        self.sessao.commit()
        self.sessao.refresh(objeto)
        return objeto

    def imovel(self, **campos):
        base = dict(
            titulo="Casa de teste",
            tipo="Casa",
            cidade="Campinas",
            estado="SP",
            valor_avaliacao=200000.0,
            valor_leilao=120000.0,
            desconto=40.0,
            area=80.0,
            quartos=2,
            banheiros=1,
            vagas=1,
            modalidade="Leilão SFI - Edital Único",
            data_primeiro_leilao=date.today() + timedelta(days=10),
        )
        base.update(campos)
        return self._salvar(Imovel(**base))

    def foto(self, imovel, url, ordem=0):
        return self._salvar(ImovelImagem(imovel_id=imovel.id, url=url, ordem=ordem))

    def perfil_corretor(self, usuario, creci="CRECI-1"):
        return self._salvar(Corretor(usuario_id=usuario.id, creci=creci))

    def anuncio(self, perfil_corretor, **campos):
        base = dict(
            corretor_id=perfil_corretor.id,
            titulo="Anúncio de teste",
            valor_mercado=100000.0,
            valor_anunciado=70000.0,
            desconto=30.0,
            status="publicado",
            ativo=True,
        )
        base.update(campos)
        return self._salvar(AnuncioImovel(**base))

    def oportunidade(self, cliente, imovel=None, corretor=None, status="interesse", **campos):
        return self._salvar(
            Oportunidade(
                imovel_id=imovel.id if imovel else None,
                cliente_id=cliente.id,
                corretor_id=corretor.id if corretor else None,
                status=status,
                valor_imovel=campos.pop("valor_imovel", 120000),
                **campos,
            )
        )

    def negociacao(self, oportunidade, status="aberta", valor=100000):
        return self._salvar(
            Negociacao(
                oportunidade_id=oportunidade.id,
                status=status,
                valor_proposto=valor,
            )
        )


@pytest.fixture()
def fabrica(sessao):
    return Fabrica(sessao)
