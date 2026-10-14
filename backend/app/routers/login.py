from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.usuario import Usuario
from app.schemas.login import Login
from app.security.password import verificar_senha
from app.security.token import criar_token

router = APIRouter(
    tags=["Login"]
)

@router.post("/login")
def login(dados: Login, db: Session = Depends(get_db)):

    usuario = (
        db.query(Usuario)
        .filter(Usuario.email == dados.email)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="E-mail ou senha invalidos."
        )

    if not verificar_senha(dados.senha, usuario.senha):
        raise HTTPException(
            status_code=401,
            detail="E-mail ou senha invalidos."
        )

    token = criar_token({
        "sub": usuario.email,
        "id": usuario.id
    })

    print("LOGIN OK")

    return {
        "access_token": token,
        "token_type": "bearer"
    }
