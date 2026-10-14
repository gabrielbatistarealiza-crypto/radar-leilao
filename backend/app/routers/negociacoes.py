from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import SessionLocal

from app.models.negociacao import Negociacao
from app.models.oportunidade import Oportunidade
from app.models.usuario import Usuario
from app.security.auth import exigir_acesso_oportunidade, usuario_atual


router = APIRouter(
    prefix="/negociacoes",
    tags=["Negociações"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


STATUS_VALIDOS = {
    "aberta",
    "contraproposta",
    "aceita",
    "recusada",
    "cancelada",
}


class NegociacaoCreate(BaseModel):
    oportunidade_id: int
    valor_proposto: Optional[float] = None
    observacoes: Optional[str] = None


class NegociacaoStatusUpdate(BaseModel):
    status: str
    valor_proposto: Optional[float] = None
    observacoes: Optional[str] = None


class NegociacaoResponse(BaseModel):
    id: int
    oportunidade_id: int
    status: str
    valor_proposto: Optional[float] = None
    observacoes: Optional[str] = None
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        from_attributes = True


@router.post(
    "",
    response_model=NegociacaoResponse,
    status_code=201,
)
def criar_negociacao(
    dados: NegociacaoCreate,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    # Verifica se a oportunidade existe
    oportunidade = (
        db.query(Oportunidade)
        .filter(Oportunidade.id == dados.oportunidade_id)
        .first()
    )

    if not oportunidade:
        raise HTTPException(
            status_code=404,
            detail="Oportunidade não encontrada.",
        )

    exigir_acesso_oportunidade(usuario_db, oportunidade)

    # Não permite negociar uma oportunidade já encerrada
    if oportunidade.status in {"concluida", "cancelada"}:
        raise HTTPException(
            status_code=400,
            detail="Esta oportunidade já está encerrada.",
        )

    # Impede mais de uma negociação ativa para a mesma oportunidade
    negociacao_ativa = (
        db.query(Negociacao)
        .filter(
            Negociacao.oportunidade_id == dados.oportunidade_id,
            Negociacao.status.in_(
                ["aberta", "contraproposta"]
            ),
        )
        .first()
    )

    if negociacao_ativa:
        raise HTTPException(
            status_code=409,
            detail="Já existe uma negociação ativa para esta oportunidade.",
        )

    negociacao = Negociacao(
        oportunidade_id=dados.oportunidade_id,
        status="aberta",
        valor_proposto=dados.valor_proposto,
        observacoes=dados.observacoes,
    )

    db.add(negociacao)

    # Ao iniciar uma negociação, atualizamos a oportunidade
    oportunidade.status = "negociando"
    oportunidade.atualizado_em = datetime.utcnow()

    db.commit()
    db.refresh(negociacao)

    return negociacao


@router.get(
    "/oportunidade/{oportunidade_id}",
    response_model=list[NegociacaoResponse],
)
def listar_negociacoes_oportunidade(
    oportunidade_id: int,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    oportunidade = (
        db.query(Oportunidade)
        .filter(Oportunidade.id == oportunidade_id)
        .first()
    )

    if not oportunidade:
        raise HTTPException(
            status_code=404,
            detail="Oportunidade não encontrada.",
        )

    exigir_acesso_oportunidade(usuario_db, oportunidade)

    return (
        db.query(Negociacao)
        .filter(
            Negociacao.oportunidade_id == oportunidade_id
        )
        .order_by(Negociacao.criado_em.desc())
        .all()
    )

@router.patch(
    "/{negociacao_id}/status",
    response_model=NegociacaoResponse,
)
def atualizar_status_negociacao(
    negociacao_id: int,
    dados: NegociacaoStatusUpdate,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    negociacao = (
        db.query(Negociacao)
        .filter(Negociacao.id == negociacao_id)
        .first()
    )

    if not negociacao:
        raise HTTPException(
            status_code=404,
            detail="Negociação não encontrada.",
        )

    oportunidade = (
        db.query(Oportunidade)
        .filter(
            Oportunidade.id == negociacao.oportunidade_id
        )
        .first()
    )

    if not oportunidade:
        raise HTTPException(
            status_code=404,
            detail="Oportunidade não encontrada.",
        )

    exigir_acesso_oportunidade(usuario_db, oportunidade)

    novo_status = dados.status.strip().lower()

    if novo_status not in STATUS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Status inválido. "
                "Use: aberta, contraproposta, aceita, "
                "recusada ou cancelada."
            ),
        )

    # Contraproposta precisa obrigatoriamente de um valor
    if novo_status == "contraproposta":
        if dados.valor_proposto is None:
            raise HTTPException(
                status_code=400,
                detail="Informe o valor da contraproposta.",
            )

        if dados.valor_proposto <= 0:
            raise HTTPException(
                status_code=400,
                detail="O valor da contraproposta deve ser maior que zero.",
            )

        negociacao.valor_proposto = dados.valor_proposto

        if dados.observacoes is not None:
            negociacao.observacoes = (
                dados.observacoes.strip() or None
            )

    negociacao.status = novo_status
    negociacao.atualizado_em = datetime.utcnow()

    # Negociação aceita encerra a oportunidade
    if novo_status == "aceita":
        oportunidade.status = "concluida"
        oportunidade.atualizado_em = datetime.utcnow()

    # Negociação recusada ou cancelada
    elif novo_status in {"recusada", "cancelada"}:
        oportunidade.status = "em_contato"
        oportunidade.atualizado_em = datetime.utcnow()

    db.commit()
    db.refresh(negociacao)

    return negociacao
