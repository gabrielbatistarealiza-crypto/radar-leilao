from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.imovel import Imovel, ImovelImagem
from app.models.negociacao import Negociacao
from app.models.operacao import Operacao
from app.models.oportunidade import Oportunidade
from app.models.usuario import Usuario
from app.routers.negociacoes import STATUS_VALIDOS as STATUS_NEGOCIACAO_VALIDOS
from app.routers.operacoes import STATUS_VALIDOS as STATUS_OPERACAO_VALIDOS
from app.routers.oportunidades import STATUS_VALIDOS as STATUS_OPORTUNIDADE_VALIDOS
from app.schemas.usuario import UsuarioCreate, UsuarioResponse, UsuarioUpdate
from app.security.auth import usuario_admin, usuario_e_admin
from app.security.password import gerar_hash
from pydantic import BaseModel


router = APIRouter(
    prefix="/admin",
    tags=["Administração"],
)


class AtribuirOportunidade(BaseModel):
    corretor_id: int


def _oportunidade_resumo(oportunidade):
    return {
        "id": oportunidade.id,
        "imovel_id": oportunidade.imovel_id,
        "anuncio_id": oportunidade.anuncio_id,
        "cliente_id": oportunidade.cliente_id,
        "corretor_id": oportunidade.corretor_id,
        "status": oportunidade.status,
        "valor_imovel": oportunidade.valor_imovel,
        "criado_em": oportunidade.criado_em,
    }


@router.get("/oportunidades/sem-corretor")
def listar_oportunidades_sem_corretor(
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    oportunidades = (
        db.query(Oportunidade)
        .filter(Oportunidade.corretor_id.is_(None))
        .filter(Oportunidade.status.in_(["interesse", "em_contato", "negociando"]))
        .order_by(Oportunidade.criado_em.asc())
        .all()
    )
    return [_oportunidade_resumo(item) for item in oportunidades]


@router.patch("/oportunidades/{oportunidade_id}/corretor")
def atribuir_oportunidade(
    oportunidade_id: int,
    dados: AtribuirOportunidade,
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    oportunidade = db.query(Oportunidade).filter(Oportunidade.id == oportunidade_id).first()
    if not oportunidade:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")
    if oportunidade.status in {"concluida", "cancelada"}:
        raise HTTPException(status_code=400, detail="Oportunidades encerradas não podem ser atribuídas.")

    corretor = db.query(Usuario).filter(Usuario.id == dados.corretor_id).first()
    if not corretor or corretor.tipo != "corretor":
        raise HTTPException(status_code=404, detail="Corretor não encontrado.")

    oportunidade.corretor_id = corretor.id
    oportunidade.atualizado_em = datetime.utcnow()
    db.commit()
    db.refresh(oportunidade)
    return _oportunidade_resumo(oportunidade)



def _contagens_por_status(db: Session, modelo):
    """Conta registros por status no banco, sem carregar linhas individuais."""
    return {
        status: quantidade
        for status, quantidade in (
            db.query(modelo.status, func.count(modelo.id))
            .group_by(modelo.status)
            .all()
        )
    }


@router.get("/dashboard")
def dashboard_admin(
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    hoje = date.today()

    total_imoveis = db.query(func.count(Imovel.id)).scalar() or 0

    condicao_ativo = (
        (
            (Imovel.data_primeiro_leilao.isnot(None))
            & (Imovel.data_primeiro_leilao >= hoje)
        )
        |
        (
            (Imovel.data_segundo_leilao.isnot(None))
            & (Imovel.data_segundo_leilao >= hoje)
        )
        |
        (
            (Imovel.data_licitacao_aberta.isnot(None))
            & (Imovel.data_licitacao_aberta >= hoje)
        )
    )

    ativos = (
        db.query(func.count(Imovel.id))
        .filter(condicao_ativo)
        .scalar()
        or 0
    )

    encerrados = (
        db.query(func.count(Imovel.id))
        .filter(
            ~condicao_ativo,
            (
                (Imovel.data_primeiro_leilao.isnot(None))
                | (Imovel.data_segundo_leilao.isnot(None))
                | (Imovel.data_licitacao_aberta.isnot(None))
            ),
        )
        .scalar()
        or 0
    )

    imoveis_com_fotos = (
        db.query(func.count(func.distinct(ImovelImagem.imovel_id)))
        .scalar()
        or 0
    )

    total_imagens = (
        db.query(func.count(ImovelImagem.id))
        .scalar()
        or 0
    )

    total_usuarios = (
        db.query(func.count(Usuario.id))
        .scalar()
        or 0
    )

    totais_usuarios = (
        db.query(
            func.coalesce(
                func.sum(case((Usuario.tipo == "cliente", 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((Usuario.tipo == "corretor", 1), else_=0)),
                0,
            ),
            # Um CASE por linha conta o usuário uma vez, mesmo se as duas
            # condições de administrador forem verdadeiras.
            func.coalesce(
                func.sum(
                    case(
                        (
                            or_(
                                Usuario.admin.is_(True),
                                Usuario.tipo == "admin",
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
        )
        .one()
    )

    contagens_oportunidades = _contagens_por_status(db, Oportunidade)
    contagens_negociacoes = _contagens_por_status(db, Negociacao)
    contagens_operacoes = _contagens_por_status(db, Operacao)

    oportunidades = {
        "total": sum(contagens_oportunidades.values()),
        **{
            status: contagens_oportunidades.get(status, 0)
            for status in sorted(STATUS_OPORTUNIDADE_VALIDOS)
        },
    }
    rotulos_negociacoes = {
        "abertas": "aberta",
        "contrapropostas": "contraproposta",
        "aceitas": "aceita",
        "recusadas": "recusada",
        "canceladas": "cancelada",
    }
    negociacoes = {
        "total": sum(contagens_negociacoes.values()),
        **{
            rotulo: contagens_negociacoes.get(status, 0)
            for rotulo, status in rotulos_negociacoes.items()
            if status in STATUS_NEGOCIACAO_VALIDOS
        },
    }
    operacoes = {
        "total": sum(contagens_operacoes.values()),
        **{
            status: contagens_operacoes.get(status, 0)
            for status in sorted(STATUS_OPERACAO_VALIDOS)
        },
    }

    return {
        "imoveis": {
            "total": total_imoveis,
            "ativos": ativos,
            "encerrados": encerrados,
        },
        "fotos": {
            "imoveis_com_fotos": imoveis_com_fotos,
            "total_imagens": total_imagens,
        },
        "usuarios": {
            "total": total_usuarios,
            "clientes": totais_usuarios[0],
            "corretores": totais_usuarios[1],
            "administradores": totais_usuarios[2],
        },
        "oportunidades": oportunidades,
        "negociacoes": negociacoes,
        "operacoes": operacoes,
    }


@router.get(
    "/usuarios",
    response_model=list[UsuarioResponse],
)
def listar_usuarios(
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    return (
        db.query(Usuario)
        .order_by(Usuario.id.asc())
        .all()
    )


@router.post(
    "/usuarios",
    response_model=UsuarioResponse,
)
def criar_usuario_admin(
    dados: UsuarioCreate,
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    existente = (
        db.query(Usuario)
        .filter(Usuario.email == dados.email)
        .first()
    )

    if existente:
        raise HTTPException(
            status_code=400,
            detail="Este e-mail já está cadastrado.",
        )

    tipo = (dados.tipo or "cliente").strip().lower()

    if tipo not in {"cliente", "corretor", "admin"}:
        raise HTTPException(
            status_code=400,
            detail="Tipo de usuário inválido.",
        )

    novo_usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha=gerar_hash(dados.senha),
        admin=(tipo == "admin"),
        tipo=tipo,
    )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    return novo_usuario


@router.patch(
    "/usuarios/{usuario_id}",
    response_model=UsuarioResponse,
)
def atualizar_usuario_admin(
    usuario_id: int,
    dados: UsuarioUpdate,
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    usuario = (
        db.query(Usuario)
        .filter(Usuario.id == usuario_id)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado.",
        )

    # E-mail
    if dados.email is not None:
        outro = (
            db.query(Usuario)
            .filter(
                Usuario.email == dados.email,
                Usuario.id != usuario_id,
            )
            .first()
        )

        if outro:
            raise HTTPException(
                status_code=400,
                detail="Este e-mail já está cadastrado.",
            )

        usuario.email = dados.email

    # Nome
    if dados.nome is not None:
        usuario.nome = dados.nome

    # Senha
    if dados.senha is not None:
        usuario.senha = gerar_hash(dados.senha)

    # Papel / tipo
    if dados.tipo is not None:
        novo_tipo = dados.tipo.strip().lower()

        if novo_tipo not in {"cliente", "corretor", "admin"}:
            raise HTTPException(
                status_code=400,
                detail="Tipo de usuário inválido.",
            )

        usuario.tipo = novo_tipo
        usuario.admin = novo_tipo == "admin"

    # Administração
    if dados.admin is not None:
        # Promover
        if dados.admin:
            usuario.admin = True
            usuario.tipo = "admin"

        # Revogar
        else:
            eh_admin_atual = usuario_e_admin(usuario)

            if eh_admin_atual:
                total_admins = (
                    db.query(Usuario)
                    .filter(
                        (Usuario.admin.is_(True))
                        | (Usuario.tipo == "admin")
                    )
                    .count()
                )

                if total_admins <= 1:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "O sistema precisa ter pelo menos "
                            "um administrador."
                        ),
                    )

            usuario.admin = False

            # Se era admin, deixa de ser admin também no tipo.
            if usuario.tipo == "admin":
                usuario.tipo = "cliente"

    db.commit()
    db.refresh(usuario)

    return usuario


@router.delete("/usuarios/{usuario_id}")
def excluir_usuario_admin(
    usuario_id: int,
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    if administrador.id == usuario_id:
        raise HTTPException(
            status_code=400,
            detail="Você não pode excluir o próprio usuário administrador.",
        )

    usuario = (
        db.query(Usuario)
        .filter(Usuario.id == usuario_id)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado.",
        )

    if usuario_e_admin(usuario):
        total_admins = (
            db.query(Usuario)
            .filter(
                (Usuario.admin.is_(True))
                | (Usuario.tipo == "admin")
            )
            .count()
        )

        if total_admins <= 1:
            raise HTTPException(
                status_code=400,
                detail="O sistema precisa ter pelo menos um administrador.",
            )

    db.delete(usuario)
    db.commit()

    return {
        "mensagem": "Usuário excluído com sucesso.",
    }
