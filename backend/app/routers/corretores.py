from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.corretor import Corretor
from app.models.usuario import Usuario
from app.security.auth import usuario_atual, usuario_e_admin


router = APIRouter(
    prefix="/corretores",
    tags=["Corretores"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class CorretorCreate(BaseModel):
    usuario_id: int
    nome_profissional: Optional[str] = None
    creci: str
    telefone: Optional[str] = None
    imobiliaria: Optional[str] = None


class CorretorResponse(BaseModel):
    id: int
    usuario_id: int
    nome_profissional: Optional[str] = None
    creci: str
    telefone: Optional[str] = None
    imobiliaria: Optional[str] = None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        from_attributes = True


@router.post(
    "",
    response_model=CorretorResponse,
    status_code=201,
)
def criar_corretor(
    dados: CorretorCreate,
    db: Session = Depends(get_db),
    usuario_atual=Depends(usuario_atual),
):
    if not usuario_e_admin(usuario_atual) and (
        usuario_atual.tipo != "corretor"
        or usuario_atual.id != dados.usuario_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Você só pode criar seu próprio perfil de corretor.",
        )

    # Verifica se o usuário existe
    usuario = (
        db.query(Usuario)
        .filter(Usuario.id == dados.usuario_id)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado.",
        )

    if usuario.tipo != "corretor":
        raise HTTPException(
            status_code=400,
            detail="O usuário relacionado precisa ter tipo corretor.",
        )

    # Um usuário só pode ter um perfil de corretor
    corretor_existente = (
        db.query(Corretor)
        .filter(Corretor.usuario_id == dados.usuario_id)
        .first()
    )

    if corretor_existente:
        raise HTTPException(
            status_code=409,
            detail="Este usuário já possui um perfil de corretor.",
        )

    # CRECI não pode estar duplicado
    creci_existente = (
        db.query(Corretor)
        .filter(Corretor.creci == dados.creci)
        .first()
    )

    if creci_existente:
        raise HTTPException(
            status_code=409,
            detail="Este CRECI já está cadastrado.",
        )

    corretor = Corretor(
        usuario_id=dados.usuario_id,
        nome_profissional=dados.nome_profissional,
        creci=dados.creci,
        telefone=dados.telefone,
        imobiliaria=dados.imobiliaria,
        ativo=True,
    )

    db.add(corretor)
    db.commit()
    db.refresh(corretor)

    return corretor


@router.get(
    "/{corretor_id}",
    response_model=CorretorResponse,
)
def obter_corretor(
    corretor_id: int,
    db: Session = Depends(get_db),
    usuario_atual=Depends(usuario_atual),
):
    corretor = (
        db.query(Corretor)
        .filter(Corretor.id == corretor_id)
        .first()
    )

    if not corretor:
        raise HTTPException(
            status_code=404,
            detail="Corretor não encontrado.",
        )

    if not usuario_e_admin(usuario_atual) and (
        usuario_atual.tipo != "corretor"
        or corretor.usuario_id != usuario_atual.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Você só pode consultar seu próprio perfil de corretor.",
        )

    return corretor


@router.get(
    "/usuario/{usuario_id}",
    response_model=CorretorResponse,
)
def obter_corretor_por_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario_atual=Depends(usuario_atual),
):
    if not usuario_e_admin(usuario_atual) and (
        usuario_atual.tipo != "corretor"
        or usuario_atual.id != usuario_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Você só pode consultar seu próprio perfil de corretor.",
        )

    corretor = (
        db.query(Corretor)
        .filter(Corretor.usuario_id == usuario_id)
        .first()
    )

    if not corretor:
        raise HTTPException(
            status_code=404,
            detail="Este usuário não possui perfil de corretor.",
        )

    return corretor
