from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.operacao import Operacao
from app.models.oportunidade import Oportunidade
from app.models.negociacao import Negociacao
from app.models.usuario import Usuario
from app.security.auth import (
    exigir_acesso_oportunidade,
    usuario_atual,
    usuario_e_admin,
    usuario_e_corretor,
)


router = APIRouter(
    prefix="/operacoes",
    tags=["Operações"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


STATUS_VALIDOS = {
    "em_andamento",
    "concluida",
    "cancelada",
}


class OperacaoCreate(BaseModel):
    oportunidade_id: int
    valor_imovel: float


class OperacaoStatusUpdate(BaseModel):
    status: str


class OperacaoResponse(BaseModel):
    id: int
    oportunidade_id: int
    valor_imovel: float
    percentual_taxa: float
    valor_taxa: float
    status: str
    criado_em: datetime
    concluido_em: datetime | None = None

    class Config:
        from_attributes = True


@router.post(
    "",
    response_model=OperacaoResponse,
    status_code=201,
)
def criar_operacao(
    dados: OperacaoCreate,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    # Verifica a oportunidade
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

    if not usuario_e_admin(usuario_db) and (
        not usuario_e_corretor(usuario_db)
        or oportunidade.corretor_id != usuario_db.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Apenas o administrador ou o corretor responsável pode criar a operação.",
        )

    # A operação só pode nascer de uma oportunidade concluída
    if oportunidade.status != "concluida":
        raise HTTPException(
            status_code=400,
            detail=(
                "A operação só pode ser criada "
                "após a negociação ser aceita."
            ),
        )

    # Verifica se já existe operação para essa oportunidade
    operacao_existente = (
        db.query(Operacao)
        .filter(
            Operacao.oportunidade_id == dados.oportunidade_id
        )
        .first()
    )

    if operacao_existente:
        raise HTTPException(
            status_code=409,
            detail="Já existe uma operação para esta oportunidade.",
        )

    # Confirma que existe uma negociação aceita
    negociacao_aceita = (
        db.query(Negociacao)
        .filter(
            Negociacao.oportunidade_id == dados.oportunidade_id,
            Negociacao.status == "aceita",
        )
        .first()
    )

    if not negociacao_aceita:
        raise HTTPException(
            status_code=400,
            detail="Não existe negociação aceita para esta oportunidade.",
        )

    if dados.valor_imovel <= 0:
        raise HTTPException(
            status_code=400,
            detail="O valor do imóvel deve ser maior que zero.",
        )

    # Percentual definido para a operação
    percentual_taxa = Decimal("10.00")

    valor_imovel = Decimal(str(dados.valor_imovel))

    # Cálculo feito no backend
    valor_taxa = (
        valor_imovel * percentual_taxa / Decimal("100")
    )

    operacao = Operacao(
        oportunidade_id=dados.oportunidade_id,
        valor_imovel=valor_imovel,
        percentual_taxa=percentual_taxa,
        valor_taxa=valor_taxa,
        status="em_andamento",
    )

    db.add(operacao)
    db.commit()
    db.refresh(operacao)

    return operacao


@router.get(
    "/oportunidade/{oportunidade_id}",
    response_model=OperacaoResponse,
)
def obter_operacao_oportunidade(
    oportunidade_id: int,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    operacao = (
        db.query(Operacao)
        .filter(
            Operacao.oportunidade_id == oportunidade_id
        )
        .first()
    )

    if not operacao:
        raise HTTPException(
            status_code=404,
            detail="Operação não encontrada.",
        )

    oportunidade = (
        db.query(Oportunidade)
        .filter(Oportunidade.id == oportunidade_id)
        .first()
    )
    if not oportunidade:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")

    exigir_acesso_oportunidade(usuario_db, oportunidade)

    return operacao


@router.patch(
    "/{operacao_id}/status",
    response_model=OperacaoResponse,
)
def atualizar_status_operacao(
    operacao_id: int,
    dados: OperacaoStatusUpdate,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    operacao = (
        db.query(Operacao)
        .filter(Operacao.id == operacao_id)
        .first()
    )

    if not operacao:
        raise HTTPException(
            status_code=404,
            detail="Operação não encontrada.",
        )

    oportunidade = (
        db.query(Oportunidade)
        .filter(Oportunidade.id == operacao.oportunidade_id)
        .first()
    )
    if not oportunidade:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")

    if not usuario_e_admin(usuario_db) and (
        not usuario_e_corretor(usuario_db)
        or oportunidade.corretor_id != usuario_db.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Apenas o administrador ou o corretor responsável pode alterar a operação.",
        )

    novo_status = dados.status.strip().lower()

    if novo_status not in STATUS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Status inválido. "
                "Use: em_andamento, concluida ou cancelada."
            ),
        )

    operacao.status = novo_status

    if novo_status == "concluida":
        operacao.concluido_em = datetime.utcnow()
    elif novo_status == "cancelada":
        operacao.concluido_em = None

    db.commit()
    db.refresh(operacao)

    return operacao
