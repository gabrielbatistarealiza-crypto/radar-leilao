"""Anúncios de imóveis: qualquer conta pode publicar; um administrador aprova.

- Não há desconto mínimo (antes exigia-se 20% abaixo do valor de mercado).
- Para publicar é preciso aceitar a comissão do site: 6% do valor de venda, paga
  pelo vendedor, se o negócio fechar pelo site (fica registada com a data).
- Um anúncio novo (ou editado por quem o publicou) fica "em análise" até um
  administrador o aprovar ("publicado") ou rejeitar ("rejeitado", com motivo).
  Os anúncios de administradores ficam publicados logo.
- Só os anúncios publicados e ativos são públicos; o dono e os administradores
  veem também os outros.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.anuncio_imagem import AnuncioImagem
from app.models.anuncio_imovel import (
    COMISSAO_SITE_PERCENTUAL,
    EM_ANALISE,
    PUBLICADO,
    REJEITADO,
    AnuncioImovel,
)
from app.models.corretor import Corretor
from app.models.usuario import Usuario
from app.schemas.anuncio_imovel import AnuncioImovelResponse
from app.security.auth import usuario_admin, usuario_atual, usuario_e_admin, usuario_opcional

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
    # corretor_id: aceite por compatibilidade com o formulário antigo, mas ignorado
    # (o perfil de corretor, se existir, vem da conta de quem publica).
    corretor_id: Optional[int] = None

    titulo: str = Field(min_length=1, max_length=255)
    tipo: Optional[str] = Field(default=None, max_length=100)

    endereco: Optional[str] = Field(default=None, max_length=255)
    cidade: Optional[str] = Field(default=None, max_length=100)
    estado: Optional[str] = Field(default=None, max_length=2)

    valor_mercado: float
    valor_anunciado: float

    area: Optional[float] = None
    quartos: Optional[int] = None
    banheiros: Optional[int] = None
    vagas: Optional[int] = None

    descricao: Optional[str] = None

    # Obrigatório ao criar: aceitar a comissão do site.
    aceito_comissao: bool = False


class Rejeicao(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


# ------------------------------------------------------------------ ajudas

def _buscar(db: Session, anuncio_id: int) -> AnuncioImovel:
    anuncio = db.query(AnuncioImovel).filter(AnuncioImovel.id == anuncio_id).first()
    if not anuncio:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado.")
    return anuncio


def _e_dono_ou_admin(usuario: Usuario | None, anuncio: AnuncioImovel) -> bool:
    return usuario is not None and (usuario_e_admin(usuario) or anuncio.usuario_id == usuario.id)


def _exigir_dono_ou_admin(usuario: Usuario, anuncio: AnuncioImovel) -> None:
    if not _e_dono_ou_admin(usuario, anuncio):
        raise HTTPException(status_code=403, detail="Só quem publicou o anúncio (ou um administrador) o pode alterar.")


def _exigir_leitura(usuario: Usuario | None, anuncio: AnuncioImovel) -> None:
    if _e_dono_ou_admin(usuario, anuncio):
        return
    if anuncio.status != PUBLICADO or not anuncio.ativo:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado.")


def _validar_valores(dados: AnuncioImovelCreate) -> float:
    """Devolve o desconto (%) sobre o valor de mercado. Não há mínimo."""
    if not dados.titulo.strip():
        raise HTTPException(status_code=400, detail="Informe um título para o anúncio.")
    if dados.valor_mercado <= 0:
        raise HTTPException(status_code=400, detail="O valor de mercado deve ser maior que zero.")
    if dados.valor_anunciado <= 0:
        raise HTTPException(status_code=400, detail="O valor anunciado deve ser maior que zero.")
    if dados.valor_anunciado > dados.valor_mercado:
        raise HTTPException(status_code=400, detail="O valor anunciado não pode ser maior que o valor de mercado.")
    return round((dados.valor_mercado - dados.valor_anunciado) / dados.valor_mercado * 100, 2)


def _aplicar_campos(anuncio: AnuncioImovel, dados: AnuncioImovelCreate, desconto: float) -> None:
    anuncio.titulo = dados.titulo.strip()
    anuncio.tipo = dados.tipo
    anuncio.endereco = dados.endereco
    anuncio.cidade = dados.cidade
    anuncio.estado = dados.estado.upper() if dados.estado else None
    anuncio.valor_mercado = dados.valor_mercado
    anuncio.valor_anunciado = dados.valor_anunciado
    anuncio.desconto = desconto
    anuncio.area = dados.area
    anuncio.quartos = dados.quartos
    anuncio.banheiros = dados.banheiros
    anuncio.vagas = dados.vagas
    anuncio.descricao = dados.descricao


def _publico(anuncio: AnuncioImovel) -> dict:
    """Campos de um anúncio publicado para quem não é o dono (sem dados de contacto)."""
    return {
        "id": anuncio.id,
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
        "fotos": [{"id": f.id, "anuncio_id": f.anuncio_id, "url": f.url, "ordem": f.ordem} for f in anuncio.fotos],
    }


# ------------------------------------------------------------------ criar / editar / apagar

@router.post("", response_model=AnuncioImovelResponse, status_code=201)
def criar_anuncio(
    dados: AnuncioImovelCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
    if not dados.aceito_comissao:
        raise HTTPException(
            status_code=400,
            detail=f"Para publicar é preciso aceitar a comissão de {COMISSAO_SITE_PERCENTUAL}% do site sobre o valor de venda.",
        )
    desconto = _validar_valores(dados)
    perfil = db.query(Corretor).filter(Corretor.usuario_id == usuario.id, Corretor.ativo.is_(True)).first()
    admin = usuario_e_admin(usuario)

    anuncio = AnuncioImovel(
        usuario_id=usuario.id,
        corretor_id=perfil.id if perfil else None,
        comissao_percentual=COMISSAO_SITE_PERCENTUAL,
        comissao_aceite_em=datetime.utcnow(),
        status=PUBLICADO if admin else EM_ANALISE,
        ativo=True,
    )
    _aplicar_campos(anuncio, dados, desconto)
    db.add(anuncio)
    db.commit()
    db.refresh(anuncio)
    return anuncio


@router.put("/{anuncio_id}", response_model=AnuncioImovelResponse)
def atualizar_anuncio(
    anuncio_id: int,
    dados: AnuncioImovelCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
    anuncio = _buscar(db, anuncio_id)
    _exigir_dono_ou_admin(usuario, anuncio)
    desconto = _validar_valores(dados)
    _aplicar_campos(anuncio, dados, desconto)
    if not usuario_e_admin(usuario):
        # Alterado por quem publicou: volta a ser revisto antes de aparecer.
        anuncio.status = EM_ANALISE
        anuncio.motivo_rejeicao = None
    anuncio.atualizado_em = datetime.utcnow()
    db.commit()
    db.refresh(anuncio)
    return anuncio


@router.delete("/{anuncio_id}", status_code=204)
def excluir_anuncio(
    anuncio_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
    anuncio = _buscar(db, anuncio_id)
    _exigir_dono_ou_admin(usuario, anuncio)
    # Oportunidades ligadas ao anúncio ficam (sem anúncio).
    from app.models.oportunidade import Oportunidade

    db.query(Oportunidade).filter(Oportunidade.anuncio_id == anuncio.id).update(
        {"anuncio_id": None}, synchronize_session=False)
    db.delete(anuncio)
    db.commit()
    return None


# ------------------------------------------------------------------ listas (antes de "/{anuncio_id}")

@router.get("/publicados")
def listar_anuncios_publicados(db: Session = Depends(get_db)):
    anuncios = (
        db.query(AnuncioImovel)
        .filter(AnuncioImovel.status == PUBLICADO, AnuncioImovel.ativo.is_(True))
        .order_by(AnuncioImovel.criado_em.desc())
        .all()
    )
    return [_publico(a) for a in anuncios]


@router.get("/meus", response_model=list[AnuncioImovelResponse])
def listar_meus_anuncios(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    return (
        db.query(AnuncioImovel)
        .filter(AnuncioImovel.usuario_id == usuario.id)
        .order_by(AnuncioImovel.criado_em.desc())
        .all()
    )


@router.get("/moderacao")
def listar_para_moderacao(
    estado: str = Query(EM_ANALISE, pattern=f"^({EM_ANALISE}|{PUBLICADO}|{REJEITADO})$"),
    db: Session = Depends(get_db),
    administrador: Usuario = Depends(usuario_admin),
):
    anuncios = (
        db.query(AnuncioImovel)
        .filter(AnuncioImovel.status == estado)
        .order_by(AnuncioImovel.criado_em.asc())
        .all()
    )
    donos = {u.id: u for u in db.query(Usuario).filter(Usuario.id.in_({a.usuario_id for a in anuncios})).all()} if anuncios else {}
    return [
        {**_publico(a), "usuario_id": a.usuario_id, "motivo_rejeicao": a.motivo_rejeicao,
         "comissao_percentual": float(a.comissao_percentual) if a.comissao_percentual is not None else None,
         "comissao_aceite_em": a.comissao_aceite_em,
         "dono": {"nome": donos[a.usuario_id].nome, "email": donos[a.usuario_id].email, "tipo": donos[a.usuario_id].tipo}
         if a.usuario_id in donos else None}
        for a in anuncios
    ]


@router.get("/corretor/{corretor_id}")
def listar_anuncios_corretor(
    corretor_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(usuario_opcional),
):
    """Compatibilidade: anúncios publicados de um perfil de corretor (o dono vê todos)."""
    corretor = db.query(Corretor).filter(Corretor.id == corretor_id).first()
    if not corretor:
        raise HTTPException(status_code=404, detail="Corretor não encontrado.")
    anuncios = (
        db.query(AnuncioImovel)
        .filter(AnuncioImovel.corretor_id == corretor_id)
        .order_by(AnuncioImovel.criado_em.desc())
        .all()
    )
    return [_publico(a) for a in anuncios if _e_dono_ou_admin(usuario, a) or (a.status == PUBLICADO and a.ativo)]


# ------------------------------------------------------------------ ficheiro de uma foto carregada

@router.get("/fotos/{chave}")
def ficheiro_da_foto(chave: str, db: Session = Depends(get_db)):
    """Bytes de uma foto carregada. Sem sessão (as <img> não enviam o token): a chave
    é aleatória (128 bits), por isso só a vê quem tem o endereço."""
    from fastapi import Response

    if len(chave) != 32 or not all(c in "0123456789abcdef" for c in chave):
        raise HTTPException(status_code=404, detail="Foto não encontrada.")
    foto = db.query(AnuncioImagem).filter(AnuncioImagem.chave == chave).first()
    if foto is None or foto.conteudo is None:
        raise HTTPException(status_code=404, detail="Foto não encontrada.")
    return Response(content=foto.conteudo, media_type=foto.tipo_mime or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})


# ------------------------------------------------------------------ moderação

@router.post("/{anuncio_id}/aprovar", response_model=AnuncioImovelResponse)
def aprovar_anuncio(anuncio_id: int, db: Session = Depends(get_db),
                    administrador: Usuario = Depends(usuario_admin)):
    anuncio = _buscar(db, anuncio_id)
    anuncio.status = PUBLICADO
    anuncio.motivo_rejeicao = None
    db.commit()
    db.refresh(anuncio)
    return anuncio


@router.post("/{anuncio_id}/rejeitar", response_model=AnuncioImovelResponse)
def rejeitar_anuncio(anuncio_id: int, dados: Rejeicao, db: Session = Depends(get_db),
                     administrador: Usuario = Depends(usuario_admin)):
    anuncio = _buscar(db, anuncio_id)
    anuncio.status = REJEITADO
    anuncio.motivo_rejeicao = dados.motivo.strip()
    db.commit()
    db.refresh(anuncio)
    return anuncio


# ------------------------------------------------------------------ um anúncio e fotos

@router.get("/{anuncio_id}")
def obter_anuncio(
    anuncio_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(usuario_opcional),
):
    anuncio = _buscar(db, anuncio_id)
    _exigir_leitura(usuario, anuncio)
    if _e_dono_ou_admin(usuario, anuncio):
        return AnuncioImovelResponse.model_validate(anuncio)
    return _publico(anuncio)


class AnuncioImagemCreate(BaseModel):
    url: str = Field(min_length=8, max_length=500, pattern=r"^https://")
    ordem: int = 0


# Fotos carregadas do computador ou do telemóvel (reduzidas no aparelho antes do envio).
MAX_FOTOS = 10
MAX_BYTES_FOTO = 2_000_000


class FotoCarregada(BaseModel):
    conteudo_base64: str = Field(min_length=16, max_length=2_800_000)
    ordem: Optional[int] = None


def _tipo_da_imagem(dados: bytes) -> str | None:
    """Tipo pelo conteúdo (não pelo nome do ficheiro): só JPEG, PNG ou WEBP."""
    if dados.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if dados.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    return None


def _foto_json(foto: AnuncioImagem) -> dict:
    return {"id": foto.id, "anuncio_id": foto.anuncio_id, "url": foto.url, "ordem": foto.ordem}


def _antes_de_nova_foto(db: Session, usuario: Usuario, anuncio: AnuncioImovel) -> int:
    """Valida o limite e devolve a ordem da próxima foto; foto nova volta a ser revista."""
    quantas = db.query(AnuncioImagem).filter(AnuncioImagem.anuncio_id == anuncio.id).count()
    if quantas >= MAX_FOTOS:
        raise HTTPException(status_code=400, detail=f"Cada anúncio pode ter no máximo {MAX_FOTOS} fotos.")
    if not usuario_e_admin(usuario) and anuncio.status == PUBLICADO:
        anuncio.status = EM_ANALISE
    return quantas


@router.post("/{anuncio_id}/fotos", status_code=201)
def adicionar_foto(
    anuncio_id: int,
    dados: AnuncioImagemCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
    anuncio = _buscar(db, anuncio_id)
    _exigir_dono_ou_admin(usuario, anuncio)
    _antes_de_nova_foto(db, usuario, anuncio)
    foto = AnuncioImagem(anuncio_id=anuncio_id, url=dados.url, ordem=dados.ordem)
    db.add(foto)
    db.commit()
    db.refresh(foto)
    return _foto_json(foto)


@router.post("/{anuncio_id}/fotos/carregar", status_code=201)
def carregar_foto(
    anuncio_id: int,
    dados: FotoCarregada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
    """Foto escolhida no aparelho, em base64 (sem dependências de upload multipart)."""
    import base64
    import binascii
    import secrets

    anuncio = _buscar(db, anuncio_id)
    _exigir_dono_ou_admin(usuario, anuncio)
    texto = dados.conteudo_base64.split(",", 1)[-1]  # aceita "data:image/jpeg;base64,..."
    try:
        conteudo = base64.b64decode(texto, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Foto inválida.")
    if len(conteudo) > MAX_BYTES_FOTO:
        raise HTTPException(status_code=400, detail="A foto é grande demais (máximo 2 MB).")
    tipo = _tipo_da_imagem(conteudo)
    if tipo is None:
        raise HTTPException(status_code=400, detail="Envie uma imagem JPG, PNG ou WEBP.")
    ordem = _antes_de_nova_foto(db, usuario, anuncio)
    chave = secrets.token_hex(16)
    foto = AnuncioImagem(
        anuncio_id=anuncio_id, ordem=dados.ordem if dados.ordem is not None else ordem,
        url=f"/anuncios-imoveis/fotos/{chave}", chave=chave, tipo_mime=tipo,
        tamanho=len(conteudo), conteudo=conteudo,
    )
    db.add(foto)
    db.commit()
    db.refresh(foto)
    return _foto_json(foto)


@router.delete("/{anuncio_id}/fotos/{foto_id}", status_code=204)
def remover_foto(
    anuncio_id: int,
    foto_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
    anuncio = _buscar(db, anuncio_id)
    _exigir_dono_ou_admin(usuario, anuncio)
    foto = db.query(AnuncioImagem).filter(AnuncioImagem.id == foto_id, AnuncioImagem.anuncio_id == anuncio_id).first()
    if not foto:
        raise HTTPException(status_code=404, detail="Foto não encontrada.")
    db.delete(foto)
    db.commit()
    return None


@router.get("/{anuncio_id}/fotos")
def listar_fotos(
    anuncio_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(usuario_opcional),
):
    anuncio = _buscar(db, anuncio_id)
    _exigir_leitura(usuario, anuncio)
    return [{"id": f.id, "anuncio_id": f.anuncio_id, "url": f.url, "ordem": f.ordem} for f in anuncio.fotos]
