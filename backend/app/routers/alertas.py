from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.criterio_alerta import CriterioAlerta
from app.models.imovel import Imovel
from app.models.notificacao import Notificacao
from app.models.oportunidade import Oportunidade
from app.models.simulacao_rentabilidade import SimulacaoRentabilidade
from app.models.usuario import Usuario
from app.routers.simulacoes_rentabilidade import CUSTOS, montar_resposta
from app.security.auth import exigir_acesso_oportunidade, usuario_atual, usuario_e_admin

router = APIRouter(prefix="/alertas", tags=["Alertas de oportunidades"])


class CriterioAlertaInput(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    desconto_minimo: Optional[Decimal] = Field(default=None, ge=0, le=100)
    preco_maximo: Optional[Decimal] = Field(default=None, gt=0)
    estado: Optional[str] = Field(default=None, min_length=2, max_length=2)
    cidade: Optional[str] = Field(default=None, max_length=100)
    roi_minimo: Optional[Decimal] = Field(default=None, ge=-100, le=10000)
    simulacao_id: Optional[int] = Field(default=None, gt=0)
    alertar_prazos_dias: int = Field(default=7, ge=0, le=90)
    ativo: bool = True

    @model_validator(mode="after")
    def validar_cenario_roi(self):
        if self.roi_minimo is not None and self.simulacao_id is None:
            raise ValueError("Selecione um cenário guardado para definir o ROI mínimo.")
        return self


class CriterioAlertaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    usuario_id: int
    nome: str
    desconto_minimo: Optional[Decimal]
    preco_maximo: Optional[Decimal]
    estado: Optional[str]
    cidade: Optional[str]
    roi_minimo: Optional[Decimal]
    simulacao_id: Optional[int]
    alertar_prazos_dias: int
    ativo: bool


def _acessar_cenario(db: Session, simulacao_id: int, usuario: Usuario):
    simulacao = db.query(SimulacaoRentabilidade).filter(SimulacaoRentabilidade.id == simulacao_id).first()
    if not simulacao:
        raise HTTPException(status_code=404, detail="Cenário de rentabilidade não encontrado.")
    oportunidade = db.query(Oportunidade).filter(Oportunidade.id == simulacao.oportunidade_id).first()
    if not oportunidade:
        raise HTTPException(status_code=404, detail="Oportunidade do cenário não encontrada.")
    exigir_acesso_oportunidade(usuario, oportunidade)
    if any(getattr(simulacao, campo) is None for campo in CUSTOS):
        raise HTTPException(status_code=422, detail="Preencha todos os custos do cenário antes de usá-lo em um alerta de ROI.")
    return simulacao


@router.get("", response_model=list[CriterioAlertaResponse])
def listar_alertas(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    return db.query(CriterioAlerta).filter(CriterioAlerta.usuario_id == usuario.id).order_by(CriterioAlerta.id.desc()).all()


@router.post("", response_model=CriterioAlertaResponse, status_code=201)
def criar_alerta(dados: CriterioAlertaInput, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    valores = dados.model_dump()
    valores["nome"] = valores["nome"].strip()
    if not valores["nome"]:
        raise HTTPException(status_code=422, detail="Informe um nome para o alerta.")
    if dados.roi_minimo is not None:
        _acessar_cenario(db, dados.simulacao_id, usuario)
    alerta = CriterioAlerta(usuario_id=usuario.id, **valores)
    db.add(alerta)
    db.commit()
    db.refresh(alerta)
    return alerta


@router.put("/{alerta_id}", response_model=CriterioAlertaResponse)
def atualizar_alerta(alerta_id: int, dados: CriterioAlertaInput, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    alerta = db.query(CriterioAlerta).filter(
        CriterioAlerta.id == alerta_id,
        CriterioAlerta.usuario_id == usuario.id,
    ).first()
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta não encontrado.")

    valores = dados.model_dump()
    valores["nome"] = valores["nome"].strip()
    if not valores["nome"]:
        raise HTTPException(status_code=422, detail="Informe um nome para o alerta.")
    if dados.roi_minimo is not None:
        _acessar_cenario(db, dados.simulacao_id, usuario)
    for campo, valor in valores.items():
        setattr(alerta, campo, valor)
    db.commit()
    db.refresh(alerta)
    return alerta


@router.delete("/{alerta_id}", status_code=204)
def excluir_alerta(alerta_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    alerta = db.query(CriterioAlerta).filter(CriterioAlerta.id == alerta_id, CriterioAlerta.usuario_id == usuario.id).first()
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta não encontrado.")
    db.delete(alerta)
    db.commit()


@router.get("/cenarios")
def listar_cenarios_alerta(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    consulta = db.query(SimulacaoRentabilidade, Oportunidade).join(Oportunidade)
    if not usuario_e_admin(usuario):
        consulta = consulta.filter((Oportunidade.cliente_id == usuario.id) | (Oportunidade.corretor_id == usuario.id))
    itens = consulta.order_by(SimulacaoRentabilidade.id.desc()).all()
    return [
        {"id": item.id, "nome": item.nome, "oportunidade_id": item.oportunidade_id,
         "imovel_id": oportunidade.imovel_id, "roi": montar_resposta(item)["roi"],
         "custos_nao_informados": montar_resposta(item)["custos_nao_informados"]}
        for item, oportunidade in itens
    ]


def _dias_ate(data):
    if data is None:
        return None
    return (data - date.today()).days


def _desconto(imovel):
    # valor_lance: o menor lance do edital (se lido) ou o preço da lista.
    if imovel.valor_avaliacao is None or imovel.valor_lance is None or imovel.valor_avaliacao <= 0:
        return None
    return (Decimal(str(imovel.valor_avaliacao)) - Decimal(str(imovel.valor_lance))) / Decimal(str(imovel.valor_avaliacao)) * 100


@router.get("/correspondencias")
def listar_correspondencias(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    criterios = db.query(CriterioAlerta).filter(CriterioAlerta.usuario_id == usuario.id, CriterioAlerta.ativo.is_(True)).all()
    if not criterios:
        return []
    imoveis = db.query(Imovel).filter(Imovel.na_lista.is_(True)).all()
    simulacoes = {}
    for criterio in criterios:
        if criterio.simulacao_id:
            simulacao = db.query(SimulacaoRentabilidade).filter(SimulacaoRentabilidade.id == criterio.simulacao_id).first()
            if simulacao:
                opp = db.query(Oportunidade).filter(Oportunidade.id == simulacao.oportunidade_id).first()
                if opp and (usuario_e_admin(usuario) or opp.cliente_id == usuario.id or opp.corretor_id == usuario.id):
                    simulacoes[criterio.id] = (simulacao, opp.imovel_id)
    resultados = []
    for imovel in imoveis:
        desconto = _desconto(imovel)
        for criterio in criterios:
            motivos = []
            filtros = []
            if criterio.desconto_minimo is not None:
                filtros.append(desconto is not None and desconto >= criterio.desconto_minimo)
                if desconto is not None and desconto >= criterio.desconto_minimo:
                    motivos.append(f"Desconto de {desconto.quantize(Decimal('0.1'))}% atende ao mínimo de {criterio.desconto_minimo}%.")
            if criterio.preco_maximo is not None:
                ok = imovel.valor_lance is not None and Decimal(str(imovel.valor_lance)) <= criterio.preco_maximo
                filtros.append(ok)
                if ok:
                    motivos.append(f"Preço de aquisição dentro do limite de R$ {criterio.preco_maximo}.")
            if criterio.estado:
                ok = (imovel.estado or "").casefold() == criterio.estado.casefold()
                filtros.append(ok)
                if ok:
                    motivos.append(f"Estado corresponde a {criterio.estado.upper()}.")
            if criterio.cidade:
                ok = (imovel.cidade or "").strip().casefold() == criterio.cidade.strip().casefold()
                filtros.append(ok)
                if ok:
                    motivos.append(f"Cidade corresponde a {imovel.cidade}.")

            pendencia = None
            roi = None
            cenario = simulacoes.get(criterio.id)
            roi_ok = criterio.roi_minimo is None
            if criterio.roi_minimo is not None:
                if not cenario or cenario[1] != imovel.id:
                    roi_ok = False
                    pendencia = "O cenário salvo não está ligado a este imóvel; ROI não comparável."
                else:
                    sim = cenario[0]
                    faltantes = [rotulo for campo, rotulo in CUSTOS.items() if getattr(sim, campo) is None]
                    if faltantes:
                        roi_ok = False
                        pendencia = "Custos incompletos no cenário: " + ", ".join(faltantes) + ". ROI não foi usado como confiável."
                    else:
                        roi = montar_resposta(sim)["roi"]
                        roi_ok = roi is not None and roi >= criterio.roi_minimo
                        if roi_ok:
                            motivos.append(f"ROI estimado de {roi.quantize(Decimal('0.1'))}% atende ao mínimo de {criterio.roi_minimo}% no cenário {sim.nome}.")
                filtros.append(roi_ok)
            filtros_ok = bool(filtros) and all(filtros)
            if criterio.roi_minimo is not None:
                filtros_ok = filtros_ok and roi_ok
            datas = [
                ("Primeiro leilão", imovel.data_primeiro_leilao),
                ("Segundo leilão", imovel.data_segundo_leilao),
                ("Licitação aberta", imovel.data_licitacao_aberta),
            ]
            prazo = [(nome, data, _dias_ate(data)) for nome, data in datas if _dias_ate(data) is not None and 0 <= _dias_ate(data) <= criterio.alertar_prazos_dias]
            # O alerta de prazo só vale para imóveis dentro dos filtros do critério
            # (estado, cidade, preço, desconto); o ROI não conta aqui.
            filtros_base = filtros[:-1] if criterio.roi_minimo is not None else filtros
            prazo_relevante = bool(prazo) and all(filtros_base)
            if prazo_relevante:
                motivos.extend([f"{nome} em {dias} dia(s) ({data.isoformat()})." for nome, data, dias in prazo])
            pendencia_custos_relevante = bool(
                pendencia and cenario and cenario[1] == imovel.id
                and any(getattr(cenario[0], campo) is None for campo in CUSTOS)
                and all(filtros[:-1] if criterio.roi_minimo is not None else filtros)
            )
            if filtros_ok or prazo_relevante or pendencia_custos_relevante:
                resultados.append({
                    "criterio_id": criterio.id, "criterio_nome": criterio.nome,
                    "imovel": {"id": imovel.id, "titulo": imovel.titulo, "cidade": imovel.cidade, "estado": imovel.estado,
                               "valor_leilao": imovel.valor_lance, "desconto": float(desconto) if desconto is not None else None,
                               "data_primeiro_leilao": imovel.data_primeiro_leilao, "data_segundo_leilao": imovel.data_segundo_leilao,
                               "data_licitacao_aberta": imovel.data_licitacao_aberta,
                               "url": imovel.url},
                    "corresponde": filtros_ok, "roi_estimado": float(roi) if roi is not None else None,
                    "pendencia_custos": pendencia, "motivos": motivos,
                    "alerta_prazo": prazo_relevante,
                })
    resultados.sort(key=lambda item: (not item["alerta_prazo"], not item["corresponde"], item["imovel"]["id"]))
    return resultados


class NotificacaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    imovel_id: int
    evento: str
    tipo: str
    titulo: str
    mensagem: str
    lida: bool
    criada_em: datetime


@router.get("/notificacoes", response_model=list[NotificacaoResponse])
def listar_notificacoes(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    return (
        db.query(Notificacao)
        .filter(Notificacao.usuario_id == usuario.id)
        .order_by(Notificacao.criada_em.desc(), Notificacao.id.desc())
        .limit(100)
        .all()
    )


@router.get("/notificacoes/nao-lidas")
def contar_notificacoes_nao_lidas(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    total = db.query(Notificacao).filter(
        Notificacao.usuario_id == usuario.id,
        Notificacao.lida.is_(False),
    ).count()
    return {"total": total}


@router.post("/notificacoes/{notificacao_id}/lida", response_model=NotificacaoResponse)
def marcar_notificacao_lida(notificacao_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    notificacao = db.query(Notificacao).filter(
        Notificacao.id == notificacao_id,
        Notificacao.usuario_id == usuario.id,
    ).first()
    if not notificacao:
        raise HTTPException(status_code=404, detail="Notificação não encontrada.")
    notificacao.lida = True
    db.commit()
    db.refresh(notificacao)
    return notificacao
