from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioResponse
from app.security.password import gerar_hash
from app.security.auth import usuario_logado

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"]
)

@router.get("/me")
def meu_usuario(usuario=Depends(usuario_logado)):
    return usuario

def criar_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db)):

    usuario_existente = (
       db.query(Usuario)
       .filter(Usuario.email == usuario.email)
       .first()
    )

    if usuario_existente:
       raise HTTPException(
          status_code=400,
          detail="Este e-mail jÃƒÂ¡ estÃƒÂ¡ cadastrado."
       )

    novo_usuario = Usuario(
        nome=usuario.nome,
        email=usuario.email,
        senha=gerar_hash(usuario.senha)
  )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    return novo_usuario
