from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import (
    UsuarioCreate,
    UsuarioResponse,
    TIPOS_USUARIO,
)
from app.security.password import gerar_hash
from app.security.auth import usuario_admin, usuario_atual


router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"]
)


@router.get("/me", response_model=UsuarioResponse)
def meu_usuario(usuario: Usuario = Depends(usuario_atual)):
    # O mesmo caminho de todas as rotas: pelo id do token.
    return usuario


@router.post("", response_model=UsuarioResponse)
def criar_usuario(
    usuario: UsuarioCreate,
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin)
):
    usuario_existente = (
        db.query(Usuario)
        .filter(Usuario.email == usuario.email)
        .first()
    )

    if usuario_existente:
        raise HTTPException(
            status_code=400,
            detail="Este e-mail já está cadastrado."
        )

    if usuario.tipo not in TIPOS_USUARIO:
        raise HTTPException(
            status_code=400,
            detail="Tipo de usuário inválido. Use: cliente, corretor ou admin."
        )

    novo_usuario = Usuario(
        nome=usuario.nome,
        email=usuario.email,
        senha=gerar_hash(usuario.senha),
        tipo=usuario.tipo,
        admin=usuario.tipo == "admin",
    )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    return novo_usuario