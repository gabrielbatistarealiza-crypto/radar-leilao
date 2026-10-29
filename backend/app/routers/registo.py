"""Registo público de clientes e pedidos de conta de corretor.

- POST /registo: qualquer pessoa cria uma conta de CLIENTE. Se mandar os dados
  de corretor, fica também um pedido PENDENTE; a conta continua a ser de
  cliente até um administrador aprovar.
- POST /pedidos-corretor e GET /pedidos-corretor/meu: um cliente já com conta
  pede para ser corretor e acompanha o pedido.
- /admin/pedidos-corretor: o administrador lista, aprova (cria o perfil com o
  CRECI e muda o tipo para "corretor") ou rejeita.

Nunca se cria uma conta de corretor ou de administrador sem um administrador.
"""
import os
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.corretor import Corretor
from app.models.oportunidade import Oportunidade
from app.models.pedido_corretor import PedidoCorretor
from app.models.usuario import Usuario
from app.routers.login import LimiteTentativasLogin
from app.security.auth import usuario_admin, usuario_atual, usuario_e_admin
from app.security.password import gerar_hash
from app.security.token import criar_token

router = APIRouter(tags=["Registo"])

STATUS_PEDIDO = ("PENDENTE", "APROVADO", "REJEITADO")

# Contas novas por processo e por hora (a API corre com um só worker). Trava
# criação em massa; o IP não serve porque atrás do proxy do Render é sempre o mesmo.
REGISTOS_POR_HORA = 30
limite_registo = LimiteTentativasLogin(maximo=REGISTOS_POR_HORA, janela=3600)

_RE_CRECI = re.compile(r"^[A-Z0-9][A-Z0-9 ./-]{2,49}$")


def registo_publico_ligado() -> bool:
    """RADAR_REGISTO_PUBLICO=0 desliga o registo público (o admin continua a criar contas)."""
    return os.getenv("RADAR_REGISTO_PUBLICO", "1").strip() != "0"


def normalizar_creci(valor: str) -> str:
    creci = " ".join(str(valor or "").upper().split())
    if not _RE_CRECI.match(creci) or not any(c.isdigit() for c in creci):
        raise ValueError("CRECI inválido. Exemplo: CRECI-SP 123456-F.")
    return creci


def _opcional(valor: Optional[str]) -> Optional[str]:
    valor = " ".join(str(valor).split()) if valor is not None else ""
    return valor or None


class DadosCorretor(BaseModel):
    creci: str = Field(max_length=60)
    nome_profissional: Optional[str] = Field(default=None, max_length=150)
    telefone: Optional[str] = Field(default=None, max_length=30)
    imobiliaria: Optional[str] = Field(default=None, max_length=150)

    @field_validator("creci")
    @classmethod
    def _creci(cls, valor):
        return normalizar_creci(valor)

    @field_validator("nome_profissional", "telefone", "imobiliaria")
    @classmethod
    def _limpar(cls, valor):
        return _opcional(valor)


class Registo(BaseModel):
    nome: str = Field(max_length=150)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=128)
    corretor: Optional[DadosCorretor] = None

    @field_validator("nome")
    @classmethod
    def _nome(cls, valor):
        nome = " ".join(valor.split())
        if len(nome) < 2:
            raise ValueError("Indique o seu nome.")
        return nome


class Rejeicao(BaseModel):
    motivo: Optional[str] = Field(default=None, max_length=500)


def _pedido_resposta(pedido: Optional[PedidoCorretor]) -> Optional[dict]:
    if pedido is None:
        return None
    return {
        "id": pedido.id,
        "usuario_id": pedido.usuario_id,
        "creci": pedido.creci,
        "nome_profissional": pedido.nome_profissional,
        "telefone": pedido.telefone,
        "imobiliaria": pedido.imobiliaria,
        "status": pedido.status,
        "motivo": pedido.motivo,
        "criado_em": pedido.criado_em,
        "decidido_em": pedido.decidido_em,
    }


def _usuario_resposta(usuario: Usuario) -> dict:
    return {
        "id": usuario.id, "nome": usuario.nome, "email": usuario.email,
        "admin": bool(usuario.admin), "tipo": usuario.tipo,
    }


def _verificar_creci_livre(db: Session, creci: str) -> None:
    em_uso = (
        db.query(Corretor.id).filter(func.upper(Corretor.creci) == creci).first()
        or db.query(PedidoCorretor.id)
        .filter(PedidoCorretor.creci == creci, PedidoCorretor.status == "PENDENTE")
        .first()
    )
    if em_uso:
        raise HTTPException(
            status_code=409,
            detail="Este CRECI já está cadastrado ou tem um pedido pendente.",
        )


def _novo_pedido(usuario_id: int, dados: DadosCorretor) -> PedidoCorretor:
    return PedidoCorretor(
        usuario_id=usuario_id,
        creci=dados.creci,
        nome_profissional=dados.nome_profissional,
        telefone=dados.telefone,
        imobiliaria=dados.imobiliaria,
        status="PENDENTE",
    )


# ------------------------------------------------------------------ público

@router.post("/registo", status_code=201)
def registar(dados: Registo, db: Session = Depends(get_db)):
    if not registo_publico_ligado():
        raise HTTPException(
            status_code=403,
            detail="O registo está fechado. Peça a conta a um administrador.",
        )

    espera = limite_registo.segundos_de_bloqueio("registo")
    if espera:
        raise HTTPException(
            status_code=429,
            detail="Muitos registos seguidos. Tente de novo mais tarde.",
            headers={"Retry-After": str(espera)},
        )

    email = dados.email.strip().lower()
    if db.query(Usuario.id).filter(func.lower(Usuario.email) == email).first():
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.")

    if dados.corretor:
        _verificar_creci_livre(db, dados.corretor.creci)

    # Sempre cliente: o tipo nunca vem do pedido.
    usuario = Usuario(
        nome=dados.nome, email=email, senha=gerar_hash(dados.senha),
        tipo="cliente", admin=False,
    )
    db.add(usuario)
    try:
        db.flush()
        pedido = None
        if dados.corretor:
            pedido = _novo_pedido(usuario.id, dados.corretor)
            db.add(pedido)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.")

    limite_registo.registar_falha("registo")  # conta o registo feito

    return {
        "access_token": criar_token({"sub": usuario.email, "id": usuario.id}),
        "token_type": "bearer",
        "usuario": _usuario_resposta(usuario),
        "pedido_corretor": _pedido_resposta(pedido),
    }


# --------------------------------------------------------- cliente com conta

@router.post("/pedidos-corretor", status_code=201)
def pedir_conta_corretor(
    dados: DadosCorretor,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
    if usuario_e_admin(usuario) or usuario.tipo != "cliente":
        raise HTTPException(
            status_code=400, detail="Só uma conta de cliente pode pedir para ser corretor."
        )

    pendente = (
        db.query(PedidoCorretor.id)
        .filter(PedidoCorretor.usuario_id == usuario.id, PedidoCorretor.status == "PENDENTE")
        .first()
    )
    if pendente:
        raise HTTPException(status_code=409, detail="Já tem um pedido pendente.")

    _verificar_creci_livre(db, dados.creci)

    pedido = _novo_pedido(usuario.id, dados)
    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    return _pedido_resposta(pedido)


@router.get("/pedidos-corretor/meu")
def meu_pedido_corretor(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
    pedido = (
        db.query(PedidoCorretor)
        .filter(PedidoCorretor.usuario_id == usuario.id)
        .order_by(PedidoCorretor.id.desc())
        .first()
    )
    return {"pedido": _pedido_resposta(pedido)}


# ------------------------------------------------------------ administrador

def _pedido_pendente(db: Session, pedido_id: int) -> PedidoCorretor:
    pedido = db.query(PedidoCorretor).filter(PedidoCorretor.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    if pedido.status != "PENDENTE":
        raise HTTPException(status_code=409, detail="Este pedido já foi decidido.")
    return pedido


@router.get("/admin/pedidos-corretor")
def listar_pedidos_corretor(
    status: Optional[str] = "PENDENTE",
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    consulta = db.query(PedidoCorretor, Usuario).join(
        Usuario, Usuario.id == PedidoCorretor.usuario_id
    )
    if status:
        status = status.strip().upper()
        if status not in STATUS_PEDIDO:
            raise HTTPException(status_code=400, detail="Status inválido.")
        consulta = consulta.filter(PedidoCorretor.status == status)

    linhas = consulta.order_by(PedidoCorretor.id.asc()).all()

    ids = [usuario.id for _, usuario in linhas]
    como_cliente = dict(
        db.query(Oportunidade.cliente_id, func.count(Oportunidade.id))
        .filter(Oportunidade.cliente_id.in_(ids))
        .group_by(Oportunidade.cliente_id)
        .all()
    ) if ids else {}

    return [
        {
            **_pedido_resposta(pedido),
            "usuario": _usuario_resposta(usuario),
            # Ao virar corretor, deixa de ver estas oportunidades como cliente.
            "oportunidades_como_cliente": como_cliente.get(usuario.id, 0),
        }
        for pedido, usuario in linhas
    ]


@router.post("/admin/pedidos-corretor/{pedido_id}/aprovar")
def aprovar_pedido_corretor(
    pedido_id: int,
    db: Session = Depends(get_db),
    administrador: Usuario = Depends(usuario_admin),
):
    pedido = _pedido_pendente(db, pedido_id)
    usuario = db.query(Usuario).filter(Usuario.id == pedido.usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if usuario_e_admin(usuario) or usuario.tipo != "cliente":
        raise HTTPException(
            status_code=409, detail="Só uma conta de cliente pode ser aprovada como corretor."
        )
    if db.query(Corretor.id).filter(Corretor.usuario_id == usuario.id).first():
        raise HTTPException(status_code=409, detail="Este usuário já tem perfil de corretor.")
    if db.query(Corretor.id).filter(func.upper(Corretor.creci) == pedido.creci).first():
        raise HTTPException(status_code=409, detail="Este CRECI já está cadastrado.")

    agora = datetime.utcnow()
    db.add(Corretor(
        usuario_id=usuario.id,
        nome_profissional=pedido.nome_profissional,
        creci=pedido.creci,
        telefone=pedido.telefone,
        imobiliaria=pedido.imobiliaria,
        ativo=True,
    ))
    usuario.tipo = "corretor"
    pedido.status = "APROVADO"
    pedido.decidido_em = agora
    pedido.decidido_por = administrador.id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Este CRECI já está cadastrado.")

    db.refresh(pedido)
    return {**_pedido_resposta(pedido), "usuario": _usuario_resposta(usuario)}


@router.post("/admin/pedidos-corretor/{pedido_id}/rejeitar")
def rejeitar_pedido_corretor(
    pedido_id: int,
    dados: Rejeicao,
    db: Session = Depends(get_db),
    administrador: Usuario = Depends(usuario_admin),
):
    pedido = _pedido_pendente(db, pedido_id)
    pedido.status = "REJEITADO"
    pedido.motivo = _opcional(dados.motivo)
    pedido.decidido_em = datetime.utcnow()
    pedido.decidido_por = administrador.id
    db.commit()
    db.refresh(pedido)
    return _pedido_resposta(pedido)
