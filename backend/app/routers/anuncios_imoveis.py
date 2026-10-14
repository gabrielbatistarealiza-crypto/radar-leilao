from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.database.database import SessionLocal
from app.models.anuncio_imovel import AnuncioImovel
from app.models.corretor import Corretor
from app.models.anuncio_imagem import AnuncioImagem
from app.models.usuario import Usuario

from app.schemas.anuncio_imovel import AnuncioImovelResponse
from app.security.auth import usuario_atual, usuario_e_admin, usuario_opcional

router = APIRouter(
    prefix="/anuncios-imoveis",
    tags=["Anúncios de Imóveis"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AnuncioImovelCreate(BaseModel):
    corretor_id: int

    titulo: str
    tipo: Optional[str] = None

    endereco: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None

    valor_mercado: float
    valor_anunciado: float

    area: Optional[float] = None
    quartos: Optional[int] = None
    banheiros: Optional[int] = None
    vagas: Optional[int] = None

    descricao: Optional[str] = None


def _exigir_corretor_proprietario(db: Session, usuario: Usuario, corretor_id: int):
    if usuario_e_admin(usuario):
        return
    if usuario.tipo != "corretor":
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores ou corretores podem gerenciar anúncios.",
        )

    # corretor_id é corretores.id; vincula-se à conta por usuario_id.
    perfil = (
        db.query(Corretor)
        .filter(Corretor.usuario_id == usuario.id)
        .first()
    )
    if not perfil or perfil.id != corretor_id:
        raise HTTPException(
            status_code=403,
            detail="O corretor só pode gerenciar os próprios anúncios.",
        )


def _exigir_leitura_anuncio(
    db: Session,
    usuario: Usuario | None,
    corretor_id: int,
    anuncio: AnuncioImovel | None = None,
):
    # Busca o anúncio quando a função é chamada apenas com o corretor_id.
    if anuncio is None:
        anuncio = (
            db.query(AnuncioImovel)
            .filter(AnuncioImovel.corretor_id == corretor_id)
            .first()
        )

    # Admin pode visualizar qualquer anúncio.
    if usuario is not None and usuario_e_admin(usuario):
        return

    # Corretor proprietário pode visualizar seus próprios anúncios.
    if usuario is not None and usuario.tipo == "corretor":
        _exigir_corretor_proprietario(db, usuario, corretor_id)
        return

    # Clientes e usuários anônimos só podem visualizar anúncios
    # publicados e ativos.
    if anuncio is None:
        raise HTTPException(
            status_code=404,
            detail="Anúncio não encontrado.",
        )

    if anuncio.status != "publicado" or not anuncio.ativo:
        raise HTTPException(
            status_code=404,
            detail="Anúncio não encontrado.",
        )

@router.post(
    "",
    response_model=AnuncioImovelResponse,
    status_code=201,
)

def criar_anuncio(
    dados: AnuncioImovelCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
    _exigir_corretor_proprietario(db, usuario, dados.corretor_id)

    # Verifica se o corretor existe
    corretor = (
        db.query(Corretor)
        .filter(Corretor.id == dados.corretor_id)
        .first()
    )

    if not corretor:
        raise HTTPException(
            status_code=404,
            detail="Corretor não encontrado.",
        )

    if not corretor.ativo:
        raise HTTPException(
            status_code=400,
            detail="Este corretor está inativo.",
        )

    # Valida os valores
    if dados.valor_mercado <= 0:
        raise HTTPException(
            status_code=400,
            detail="O valor de mercado deve ser maior que zero.",
        )

    if dados.valor_anunciado <= 0:
        raise HTTPException(
            status_code=400,
            detail="O valor anunciado deve ser maior que zero.",
        )

    if dados.valor_anunciado > dados.valor_mercado:
        raise HTTPException(
            status_code=400,
            detail=(
                "O valor anunciado não pode ser maior "
                "que o valor de mercado."
            ),
        )

    # Calcula o desconto
    desconto = (
        (dados.valor_mercado - dados.valor_anunciado)
        / dados.valor_mercado
    ) * 100

    # Regra principal do marketplace:
    # mínimo de 20% abaixo do valor de mercado
    if desconto < 20:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Imóvel não atende ao critério da plataforma. "
                f"Desconto calculado: {desconto:.2f}%. "
                f"O mínimo exigido é 20%."
            ),
        )

    anuncio = AnuncioImovel(
        corretor_id=dados.corretor_id,
        titulo=dados.titulo,
        tipo=dados.tipo,
        endereco=dados.endereco,
        cidade=dados.cidade,
        estado=dados.estado,
        valor_mercado=dados.valor_mercado,
        valor_anunciado=dados.valor_anunciado,
        desconto=desconto,
        area=dados.area,
        quartos=dados.quartos,
        banheiros=dados.banheiros,
        vagas=dados.vagas,
        descricao=dados.descricao,
        status="publicado",
        ativo=True,
    )

    db.add(anuncio)
    db.commit()
    db.refresh(anuncio)

    return anuncio

@router.put(
    "/{anuncio_id}",
    response_model=AnuncioImovelResponse,
)
def atualizar_anuncio(
    anuncio_id: int,
    dados: AnuncioImovelCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
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

    _exigir_corretor_proprietario(
        db,
        usuario,
        anuncio.corretor_id,
    )

    if dados.corretor_id != anuncio.corretor_id:
        raise HTTPException(
            status_code=400,
            detail="Não é permitido alterar o proprietário do anúncio.",
        )

    if dados.valor_mercado <= 0:
        raise HTTPException(
            status_code=400,
            detail="O valor de mercado deve ser maior que zero.",
        )

    if dados.valor_anunciado <= 0:
        raise HTTPException(
            status_code=400,
            detail="O valor anunciado deve ser maior que zero.",
        )

    anuncio.titulo = dados.titulo
    anuncio.tipo = dados.tipo
    anuncio.endereco = dados.endereco
    anuncio.cidade = dados.cidade
    anuncio.estado = dados.estado
    anuncio.valor_mercado = dados.valor_mercado
    anuncio.valor_anunciado = dados.valor_anunciado
    anuncio.area = dados.area
    anuncio.quartos = dados.quartos
    anuncio.banheiros = dados.banheiros
    anuncio.vagas = dados.vagas
    anuncio.descricao = dados.descricao

    anuncio.desconto = round(
        (1 - (dados.valor_anunciado / dados.valor_mercado)) * 100,
        2,
    )

    anuncio.atualizado_em = datetime.utcnow()

    db.commit()
    db.refresh(anuncio)

    return anuncio

@router.delete(
    "/{anuncio_id}",
    status_code=204,
)
def excluir_anuncio(
    anuncio_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
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

    _exigir_corretor_proprietario(
        db,
        usuario,
        anuncio.corretor_id,
    )

    db.delete(anuncio)
    db.commit()

    return None

@router.get(
    "/publicados",
)
def listar_anuncios_publicados(
    db: Session = Depends(get_db),
):
    anuncios = (
        db.query(AnuncioImovel)
        .filter(
            AnuncioImovel.status == "publicado",
            AnuncioImovel.ativo.is_(True),
        )
        .order_by(AnuncioImovel.criado_em.desc())
        .all()
    )

    return [
        {
            "id": anuncio.id,
            "corretor_id": anuncio.corretor_id,
            "titulo": anuncio.titulo,
            "tipo": anuncio.tipo,
            "endereco": anuncio.endereco,
            "cidade": anuncio.cidade,
            "estado": anuncio.estado,
            "valor_mercado": anuncio.valor_mercado,
            "valor_anunciado": anuncio.valor_anunciado,
            "desconto": anuncio.desconto,
            "area": anuncio.area,
            "quartos": anuncio.quartos,
            "banheiros": anuncio.banheiros,
            "vagas": anuncio.vagas,
            "descricao": anuncio.descricao,
            "status": anuncio.status,
            "ativo": anuncio.ativo,
            "criado_em": anuncio.criado_em,
            "atualizado_em": anuncio.atualizado_em,
            "fotos": [
                {
                    "id": foto.id,
                    "anuncio_id": foto.anuncio_id,
                    "url": foto.url,
                    "ordem": foto.ordem,
                }
                for foto in anuncio.fotos
            ],
        }
        for anuncio in anuncios
    ]

@router.get(
    "/{anuncio_id}",
    response_model=AnuncioImovelResponse,
)
def obter_anuncio(
    anuncio_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(usuario_opcional),
):
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

    _exigir_leitura_anuncio(
        db,
        usuario,
        anuncio.corretor_id,
        anuncio,
    )

    return anuncio



@router.get(
    "/corretor/{corretor_id}",
    response_model=list[AnuncioImovelResponse],
)
def listar_anuncios_corretor(
    corretor_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(usuario_opcional),
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

    _exigir_leitura_anuncio(db, usuario, corretor_id)

    query = (
    db.query(AnuncioImovel)
    .filter(
        AnuncioImovel.corretor_id == corretor_id
    )
)

# Clientes e usuários anônimos só veem anúncios
# publicados e ativos.
    if usuario is None or usuario.tipo == "cliente":
        query = query.filter(
            AnuncioImovel.status == "publicado",
            AnuncioImovel.ativo.is_(True),
        )

    return (
        query
        .order_by(AnuncioImovel.criado_em.desc())
        .all()
    )

class AnuncioImagemCreate(BaseModel):
    url: str
    ordem: int = 0

@router.post(
    "/{anuncio_id}/fotos",
    status_code=201,
)
def adicionar_foto(
    anuncio_id: int,
    dados: AnuncioImagemCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
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

    _exigir_corretor_proprietario(
        db,
        usuario,
        anuncio.corretor_id,
    )

    foto = AnuncioImagem(
        anuncio_id=anuncio_id,
        url=dados.url,
        ordem=dados.ordem,
    )

    db.add(foto)
    db.commit()
    db.refresh(foto)

    return {
        "id": foto.id,
        "anuncio_id": foto.anuncio_id,
        "url": foto.url,
        "ordem": foto.ordem,
    }

@router.get(
    "/publicados",
    response_model=list[AnuncioImovelResponse],
)
def listar_anuncios_publicados(
    db: Session = Depends(get_db),
):
    return (
        db.query(AnuncioImovel)
        .filter(
            AnuncioImovel.status == "publicado",
            AnuncioImovel.ativo.is_(True),
        )
        .order_by(AnuncioImovel.criado_em.desc())
        .all()
    )

@router.get("/{anuncio_id}/fotos")
def listar_fotos(
    anuncio_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(usuario_opcional),
):
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

    _exigir_leitura_anuncio(
        db,
        usuario,
        anuncio.corretor_id,
    )

    return [
        {
            "id": foto.id,
            "anuncio_id": foto.anuncio_id,
            "url": foto.url,
            "ordem": foto.ordem,
        }
        for foto in anuncio.fotos
    ]