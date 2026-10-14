from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.oportunidade import Oportunidade
from app.models.simulacao_rentabilidade import SimulacaoRentabilidade
from app.models.usuario import Usuario
from app.security.auth import exigir_acesso_oportunidade, usuario_atual

router = APIRouter(prefix="/oportunidades", tags=["Simulações de rentabilidade"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SimulacaoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    preco_aquisicao: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    impostos_taxas: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    custos_juridicos: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    reformas: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    outras_despesas: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    valor_revenda: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    observacoes: Optional[str] = Field(default=None, max_length=5000)


class SimulacaoResponse(SimulacaoCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    oportunidade_id: int
    criado_por_id: Optional[int]
    criado_em: datetime
    custo_total: Decimal
    lucro_estimado: Decimal
    margem_revenda: Optional[Decimal]
    roi: Optional[Decimal]
    custos_nao_informados: list[str]


CUSTOS = {
    "impostos_taxas": "Impostos e taxas",
    "custos_juridicos": "Custos jurídicos",
    "reformas": "Reformas",
    "outras_despesas": "Outras despesas",
}


def montar_resposta(simulacao):
    custos = [getattr(simulacao, campo) or Decimal("0") for campo in CUSTOS]
    total = (simulacao.preco_aquisicao or Decimal("0")) + sum(custos, Decimal("0"))
    lucro = simulacao.valor_revenda - total
    margem = (lucro / simulacao.valor_revenda * 100) if simulacao.valor_revenda else None
    roi = (lucro / total * 100) if total else None
    resultado = {campo: getattr(simulacao, campo) for campo in SimulacaoCreate.model_fields}
    resultado.update({
        "id": simulacao.id,
        "oportunidade_id": simulacao.oportunidade_id,
        "criado_por_id": simulacao.criado_por_id,
        "criado_em": simulacao.criado_em,
        "custo_total": total,
        "lucro_estimado": lucro,
        "margem_revenda": margem,
        "roi": roi,
        "custos_nao_informados": [rotulo for campo, rotulo in CUSTOS.items() if getattr(simulacao, campo) is None],
    })
    return resultado


def obter_oportunidade(db, oportunidade_id, usuario):
    oportunidade = db.query(Oportunidade).filter(Oportunidade.id == oportunidade_id).first()
    if not oportunidade:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")
    exigir_acesso_oportunidade(usuario, oportunidade)
    return oportunidade


@router.get("/{oportunidade_id}/simulacoes", response_model=list[SimulacaoResponse])
def listar_simulacoes(oportunidade_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    obter_oportunidade(db, oportunidade_id, usuario)
    itens = db.query(SimulacaoRentabilidade).filter(
        SimulacaoRentabilidade.oportunidade_id == oportunidade_id
    ).order_by(SimulacaoRentabilidade.criado_em.desc(), SimulacaoRentabilidade.id.desc()).all()
    return [montar_resposta(item) for item in itens]


@router.post("/{oportunidade_id}/simulacoes", response_model=SimulacaoResponse, status_code=201)
def criar_simulacao(oportunidade_id: int, dados: SimulacaoCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    obter_oportunidade(db, oportunidade_id, usuario)
    valores = dados.model_dump()
    valores["nome"] = valores["nome"].strip()
    if not valores["nome"]:
        raise HTTPException(status_code=422, detail="Informe um nome para o cenário.")
    simulacao = SimulacaoRentabilidade(
        oportunidade_id=oportunidade_id, criado_por_id=usuario.id, **valores
    )
    db.add(simulacao)
    db.commit()
    db.refresh(simulacao)
    return montar_resposta(simulacao)
