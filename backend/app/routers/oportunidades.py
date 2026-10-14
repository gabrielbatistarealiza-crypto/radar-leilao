from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.imovel import Imovel
from app.models.negociacao import Negociacao
from app.models.operacao import Operacao
from app.models.oportunidade import Oportunidade
from app.models.atividade_oportunidade import AtividadeOportunidade
from app.models.usuario import Usuario
from app.models.anuncio_imovel import AnuncioImovel
from app.models.corretor import Corretor

from app.routers.negociacoes import STATUS_VALIDOS as STATUS_NEGOCIACAO_VALIDOS
from app.routers.operacoes import STATUS_VALIDOS as STATUS_OPERACAO_VALIDOS
from app.security.auth import (
    exigir_acesso_oportunidade,
    usuario_atual,
    usuario_e_admin,
    usuario_e_corretor,
)


router = APIRouter(
    prefix="/oportunidades",
    tags=["Oportunidades"],
)

STATUS_VALIDOS = {
    "interesse",
    "em_contato",
    "negociando",
    "concluida",
    "cancelada",
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _contagens_por_status(db: Session, modelo, coluna_filtro, valor_filtro, status_validos):
    linhas = (
        db.query(modelo.status, func.count(modelo.id))
        .join(Oportunidade, modelo.oportunidade_id == Oportunidade.id)
        .filter(coluna_filtro == valor_filtro)
        .group_by(modelo.status)
        .all()
    )
    por_status = {status: 0 for status in sorted(status_validos)}
    total = 0
    for status, quantidade in linhas:
        total += quantidade
        if status is not None:
            # Preserva transparência para dados legados inesperados, sem
            # incluí-los na lista de status válidos do fluxo.
            por_status[status] = quantidade
    return {"total": total, "por_status": por_status}


def _dashboard_oportunidades(db: Session, coluna_proprietario, proprietario_id: int):
    linhas_oportunidades = (
        db.query(Oportunidade.status, func.count(Oportunidade.id))
        .filter(coluna_proprietario == proprietario_id)
        .group_by(Oportunidade.status)
        .all()
    )
    oportunidades_por_status = {status: 0 for status in sorted(STATUS_VALIDOS)}
    total_oportunidades = 0
    for status, quantidade in linhas_oportunidades:
        total_oportunidades += quantidade
        if status is not None:
            oportunidades_por_status[status] = quantidade

    negociacoes = _contagens_por_status(
        db,
        Negociacao,
        coluna_proprietario,
        proprietario_id,
        STATUS_NEGOCIACAO_VALIDOS,
    )
    operacoes = _contagens_por_status(
        db,
        Operacao,
        coluna_proprietario,
        proprietario_id,
        STATUS_OPERACAO_VALIDOS,
    )

    return {
        "oportunidades": {
            "total": total_oportunidades,
            "por_status": oportunidades_por_status,
        },
        "negociacoes": negociacoes,
        "operacoes": operacoes,
    }


@router.get("/corretor/{corretor_id}/dashboard")
def dashboard_corretor(
    corretor_id: int,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    if not usuario_e_admin(usuario_db) and (
        not usuario_e_corretor(usuario_db)
        or usuario_db.id != corretor_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Você só pode consultar seu próprio dashboard de corretor.",
        )

    return _dashboard_oportunidades(
        db,
        Oportunidade.corretor_id,
        corretor_id,
    )


@router.get("/cliente/{cliente_id}/dashboard")
def dashboard_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    if not usuario_e_admin(usuario_db) and (
        getattr(usuario_db, "tipo", None) != "cliente"
        or usuario_db.id != cliente_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Você só pode consultar seu próprio dashboard de cliente.",
        )

    return _dashboard_oportunidades(
        db,
        Oportunidade.cliente_id,
        cliente_id,
    )


class OportunidadeStatusUpdate(BaseModel):
    status: str


class AtividadeCreate(BaseModel):
    tipo: str
    descricao: str
    canal: Optional[str] = None


class AtividadeResponse(BaseModel):
    id: int
    oportunidade_id: int
    tipo: str
    canal: Optional[str]
    descricao: str
    status_anterior: Optional[str]
    status_novo: Optional[str]
    criado_por_id: Optional[int]
    criado_em: datetime

    class Config:
        from_attributes = True


class OportunidadeCreate(BaseModel):
    imovel_id: int | None = None
    anuncio_id: int | None = None
    cliente_id: int
    corretor_id: int | None = None
    valor_imovel: float | None = None
    observacoes: str | None = None


class OportunidadeResponse(BaseModel):
    id: int
    imovel_id: int | None
    anuncio_id: int | None
    cliente_id: int
    corretor_id: int | None
    status: str
    valor_imovel: float | None
    observacoes: str | None
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        from_attributes = True


@router.post(
    "",
    response_model=OportunidadeResponse,
    status_code=201,
)
def criar_oportunidade(
    dados: OportunidadeCreate,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    # A oportunidade deve estar ligada a exatamente uma origem:
    # imóvel da Caixa OU anúncio de corretor.
    if dados.imovel_id is None and dados.anuncio_id is None:
        raise HTTPException(
            status_code=400,
            detail="Informe imovel_id ou anuncio_id.",
        )

    if dados.imovel_id is not None and dados.anuncio_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Informe apenas imovel_id ou anuncio_id.",
        )

    corretor_id = dados.corretor_id

    if usuario_e_admin(usuario_db):
        pass

    elif usuario_e_corretor(usuario_db):
        if corretor_id is not None and corretor_id != usuario_db.id:
            raise HTTPException(
                status_code=403,
                detail="O corretor só pode atribuir a oportunidade a si mesmo.",
            )
        corretor_id = usuario_db.id

    elif getattr(usuario_db, "tipo", None) == "cliente":
        if usuario_db.id != dados.cliente_id:
            raise HTTPException(
                status_code=403,
                detail="Você não pode criar uma oportunidade para outro cliente.",
            )

        if corretor_id is not None:
            raise HTTPException(
                status_code=403,
                detail="Clientes não podem atribuir corretores à oportunidade.",
            )

    else:
        raise HTTPException(
            status_code=403,
            detail="Tipo de usuário sem permissão.",
        )

    # Verifica se o cliente existe
    cliente = (
        db.query(Usuario)
        .filter(Usuario.id == dados.cliente_id)
        .first()
    )

    if not cliente:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado.",
        )

    if (
        not usuario_e_admin(usuario_db)
        and getattr(cliente, "tipo", None) != "cliente"
    ):
        raise HTTPException(
            status_code=403,
            detail="Oportunidades só podem ser criadas para clientes.",
        )

    # ==========================================================
    # OPORTUNIDADE DE IMÓVEL DA CAIXA
    # ==========================================================
    if dados.imovel_id is not None:

        imovel = (
            db.query(Imovel)
            .filter(Imovel.id == dados.imovel_id)
            .first()
        )

        if not imovel:
            raise HTTPException(
                status_code=404,
                detail="Imóvel não encontrado.",
            )

        # Verifica o corretor, quando informado
        if dados.corretor_id is not None:
            corretor = (
                db.query(Usuario)
                .filter(Usuario.id == dados.corretor_id)
                .first()
            )

            if not corretor:
                raise HTTPException(
                    status_code=404,
                    detail="Corretor não encontrado.",
                )

            if corretor.tipo != "corretor":
                raise HTTPException(
                    status_code=400,
                    detail="O usuário informado não é um corretor.",
                )

        # Evita oportunidade ativa duplicada
        oportunidade_existente = (
            db.query(Oportunidade)
            .filter(
                Oportunidade.imovel_id == dados.imovel_id,
                Oportunidade.cliente_id == dados.cliente_id,
                Oportunidade.status.in_(
                    ["interesse", "em_contato", "negociando"]
                ),
            )
            .first()
        )

        if oportunidade_existente:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Já existe uma oportunidade ativa "
                    "para este cliente e imóvel."
                ),
            )

        valor_imovel = (
            dados.valor_imovel
            if dados.valor_imovel is not None
            else imovel.valor_avaliacao
        )

        oportunidade = Oportunidade(
            imovel_id=dados.imovel_id,
            anuncio_id=None,
            cliente_id=dados.cliente_id,
            corretor_id=corretor_id,
            status="interesse",
            valor_imovel=valor_imovel,
            observacoes=dados.observacoes,
        )

    # ==========================================================
    # OPORTUNIDADE DE ANÚNCIO DE CORRETOR
    # ==========================================================
    else:

        anuncio = (
            db.query(AnuncioImovel)
            .filter(AnuncioImovel.id == dados.anuncio_id)
            .first()
        )

        if not anuncio:
            raise HTTPException(
                status_code=404,
                detail="Anúncio não encontrado.",
            )

        # O cliente só pode demonstrar interesse
        # em anúncio publicado e ativo.
        if anuncio.status != "publicado" or not anuncio.ativo:
            raise HTTPException(
                status_code=400,
                detail="Este anúncio não está disponível.",
            )

        # O anúncio pertence ao corretor responsável.
        # Oportunidade deve ser atribuída ao usuário
        # daquele corretor.
        corretor_anuncio = (
            db.query(Corretor)
            .filter(Corretor.id == anuncio.corretor_id)
            .first()
        )

        if not corretor_anuncio:
            raise HTTPException(
                status_code=404,
                detail="Corretor do anúncio não encontrado.",
            )

        corretor_id = corretor_anuncio.usuario_id

        # Evita oportunidade ativa duplicada
        oportunidade_existente = (
            db.query(Oportunidade)
            .filter(
                Oportunidade.anuncio_id == dados.anuncio_id,
                Oportunidade.cliente_id == dados.cliente_id,
                Oportunidade.status.in_(
                    ["interesse", "em_contato", "negociando"]
                ),
            )
            .first()
        )

        if oportunidade_existente:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Você já demonstrou interesse "
                    "neste anúncio."
                ),
            )

        valor_imovel = (
            dados.valor_imovel
            if dados.valor_imovel is not None
            else anuncio.valor_anunciado
        )

        oportunidade = Oportunidade(
            imovel_id=None,
            anuncio_id=dados.anuncio_id,
            cliente_id=dados.cliente_id,
            corretor_id=corretor_id,
            status="interesse",
            valor_imovel=valor_imovel,
            observacoes=dados.observacoes,
        )

    db.add(oportunidade)
    db.commit()
    db.refresh(oportunidade)

    return oportunidade

@router.post(
    "/anuncio/{anuncio_id}/interesse",
    response_model=OportunidadeResponse,
    status_code=201,
)
@router.post(
    "/anuncio/{anuncio_id}/interesse",
    response_model=OportunidadeResponse,
    status_code=201,
)
def demonstrar_interesse_anuncio(
    anuncio_id: int,
    db: Session = Depends(get_db),
    usuario_atual: dict = Depends(usuario_atual),
):
    # Dados do usuário autenticado
    usuario_id = usuario_atual.get("id")
    tipo_usuario = usuario_atual.get("tipo")
    admin = usuario_atual.get("admin", False)

    if not usuario_id:
        raise HTTPException(
            status_code=401,
            detail="Usuário não autenticado.",
        )

    # Somente clientes podem demonstrar interesse
    if tipo_usuario != "cliente" and not admin:
        raise HTTPException(
            status_code=403,
            detail="Apenas clientes podem demonstrar interesse em anúncios.",
        )

    # Busca o anúncio
    anuncio = (
        db.query(AnuncioImovel)
        .filter(AnuncioImovel.id == anuncio_id)
        .first()
    )

    if not anuncio:
        raise HTTPException(
            status_code=404,
            detail="Anúncio não encontrado.",
        )

    # O anúncio precisa estar publicado e ativo
    if anuncio.status != "publicado" or not anuncio.ativo:
        raise HTTPException(
            status_code=400,
            detail="Este anúncio não está disponível.",
        )

    # Busca o perfil do corretor responsável
    corretor = (
        db.query(Corretor)
        .filter(Corretor.id == anuncio.corretor_id)
        .first()
    )

    if not corretor:
        raise HTTPException(
            status_code=404,
            detail="Corretor do anúncio não encontrado.",
        )

    # Impede interesse duplicado ativo
    oportunidade_existente = (
        db.query(Oportunidade)
        .filter(
            Oportunidade.anuncio_id == anuncio_id,
            Oportunidade.cliente_id == usuario_id,
            Oportunidade.status.notin_(
                ["cancelada", "concluida"]
            ),
        )
        .first()
    )

    if oportunidade_existente:
        raise HTTPException(
            status_code=409,
            detail="Você já demonstrou interesse neste anúncio.",
        )

    oportunidade = Oportunidade(
        imovel_id=None,
        anuncio_id=anuncio.id,
        cliente_id=usuario_id,
        corretor_id=corretor.usuario_id,
        status="interesse",
        valor_imovel=anuncio.valor_anunciado,
        observacoes=None,
    )

    db.add(oportunidade)
    db.commit()
    db.refresh(oportunidade)

    return oportunidade


@router.get(
    "/cliente/{cliente_id}",
    response_model=list[OportunidadeResponse],
)
def listar_oportunidades_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    if (
        getattr(usuario_db, "tipo", None) == "cliente"
        and usuario_db.id != cliente_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Você não pode acessar oportunidades de outro cliente.",
        )

    consulta = db.query(Oportunidade).filter(Oportunidade.cliente_id == cliente_id)
    if usuario_e_corretor(usuario_db) and not usuario_e_admin(usuario_db):
        consulta = consulta.filter(Oportunidade.corretor_id == usuario_db.id)
    elif not usuario_e_admin(usuario_db) and getattr(usuario_db, "tipo", None) != "cliente":
        raise HTTPException(status_code=403, detail="Tipo de usuário sem permissão.")

    oportunidades = consulta.order_by(Oportunidade.criado_em.desc()).all()
    if usuario_e_corretor(usuario_db) and not usuario_e_admin(usuario_db) and not oportunidades:
        existe_oportunidade = (
            db.query(Oportunidade.id)
            .filter(Oportunidade.cliente_id == cliente_id)
            .first()
        )
        if existe_oportunidade:
            raise HTTPException(
                status_code=403,
                detail="Você não pode acessar oportunidades não atribuídas a você.",
            )
    return oportunidades


@router.get(
    "/corretor/{corretor_id}",
    response_model=list[OportunidadeResponse],
)
def listar_oportunidades_corretor(
    corretor_id: int,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    if not usuario_e_admin(usuario_db):
        if (
            not usuario_e_corretor(usuario_db)
            or usuario_db.id != corretor_id
        ):
            raise HTTPException(
                status_code=403,
                detail="Você só pode acessar as oportunidades atribuídas a você.",
            )

    return (
        db.query(Oportunidade)
        .filter(Oportunidade.corretor_id == corretor_id)
        .order_by(Oportunidade.criado_em.desc())
        .all()
    )


@router.get(
    "/imovel/{imovel_id}",
    response_model=list[OportunidadeResponse],
)
def listar_oportunidades_imovel(
    imovel_id: int,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    consulta = (
        db.query(Oportunidade)
        .filter(Oportunidade.imovel_id == imovel_id)
    )

    if (
        getattr(usuario_db, "tipo", None) == "cliente"
        and not usuario_e_admin(usuario_db)
    ):
        consulta = consulta.filter(
            Oportunidade.cliente_id == usuario_db.id
        )
    elif usuario_e_corretor(usuario_db) and not usuario_e_admin(usuario_db):
        consulta = consulta.filter(Oportunidade.corretor_id == usuario_db.id)
    elif not usuario_e_admin(usuario_db):
        raise HTTPException(status_code=403, detail="Tipo de usuário sem permissão.")

    oportunidades = consulta.order_by(Oportunidade.criado_em.desc()).all()
    if not oportunidades and not usuario_e_admin(usuario_db):
        existe_oportunidade = (
            db.query(Oportunidade.id)
            .filter(Oportunidade.imovel_id == imovel_id)
            .first()
        )
        if existe_oportunidade:
            raise HTTPException(
                status_code=403,
                detail="Você não pode acessar oportunidades não atribuídas a você.",
            )
    return oportunidades

@router.patch(
    "/{oportunidade_id}/status",
    response_model=OportunidadeResponse,
)
def atualizar_status_oportunidade(
    oportunidade_id: int,
    dados: OportunidadeStatusUpdate,
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

    if not usuario_e_admin(usuario_db) and not (
        usuario_e_corretor(usuario_db)
        and oportunidade.corretor_id == usuario_db.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Sem permissão para alterar esta oportunidade.",
        )

    novo_status = dados.status.strip().lower()

    if novo_status not in STATUS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Status inválido. "
                "Use: interesse, em_contato, negociando, "
                "concluida ou cancelada."
            ),
        )

    if novo_status != oportunidade.status:
        db.add(AtividadeOportunidade(
            oportunidade_id=oportunidade.id,
            tipo="status",
            descricao="Status comercial alterado.",
            status_anterior=oportunidade.status,
            status_novo=novo_status,
            criado_por_id=usuario_db.id,
        ))
        oportunidade.status = novo_status
        oportunidade.atualizado_em = datetime.utcnow()

    db.commit()
    db.refresh(oportunidade)

    return oportunidade


def _oportunidade_para_atividade(oportunidade_id: int, db: Session, usuario: Usuario):
    oportunidade = (
        db.query(Oportunidade)
        .filter(Oportunidade.id == oportunidade_id)
        .first()
    )
    if not oportunidade:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")
    if not usuario_e_admin(usuario) and not (
        usuario_e_corretor(usuario) and oportunidade.corretor_id == usuario.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Somente o corretor atribuído ou um administrador pode acessar o histórico.",
        )
    return oportunidade


@router.get(
    "/{oportunidade_id}/atividades",
    response_model=list[AtividadeResponse],
)
def listar_atividades_oportunidade(
    oportunidade_id: int,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    _oportunidade_para_atividade(oportunidade_id, db, usuario_db)
    return (
        db.query(AtividadeOportunidade)
        .filter(AtividadeOportunidade.oportunidade_id == oportunidade_id)
        .order_by(AtividadeOportunidade.criado_em.desc(), AtividadeOportunidade.id.desc())
        .all()
    )


@router.post(
    "/{oportunidade_id}/atividades",
    response_model=AtividadeResponse,
    status_code=201,
)
def criar_atividade_oportunidade(
    oportunidade_id: int,
    dados: AtividadeCreate,
    db: Session = Depends(get_db),
    usuario_db: Usuario = Depends(usuario_atual),
):
    _oportunidade_para_atividade(oportunidade_id, db, usuario_db)
    tipo = dados.tipo.strip().lower()
    descricao = dados.descricao.strip()
    canal = dados.canal.strip().lower() if dados.canal else None
    if tipo not in {"contato", "nota"}:
        raise HTTPException(status_code=400, detail="Tipo deve ser contato ou nota.")
    if not descricao:
        raise HTTPException(status_code=400, detail="A descrição não pode ficar vazia.")
    if len(descricao) > 5000:
        raise HTTPException(status_code=400, detail="A descrição deve ter até 5.000 caracteres.")
    if tipo == "contato" and canal not in {"telefone", "whatsapp", "email", "presencial", "outro"}:
        raise HTTPException(status_code=400, detail="Informe um canal de contato válido.")
    if tipo == "nota":
        canal = None

    atividade = AtividadeOportunidade(
        oportunidade_id=oportunidade_id,
        tipo=tipo,
        canal=canal,
        descricao=descricao,
        criado_por_id=usuario_db.id,
    )
    db.add(atividade)
    db.commit()
    db.refresh(atividade)
    return atividade
