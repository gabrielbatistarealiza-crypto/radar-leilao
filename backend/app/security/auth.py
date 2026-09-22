from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.usuario import Usuario
from app.security.token import SECRET_KEY, ALGORITHM


security = HTTPBearer()


def usuario_logado(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token invalido."
        )


def usuario_admin(
    usuario=Depends(usuario_logado),
    db: Session = Depends(get_db)
):
    email = usuario.get("sub")

    if not email:
        raise HTTPException(
            status_code=401,
            detail="Token invalido."
        )

    usuario_db = (
        db.query(Usuario)
        .filter(Usuario.email == email)
        .first()
    )

    if not usuario_db:
        raise HTTPException(
            status_code=401,
            detail="Usuario nao encontrado."
        )

    if not usuario_db.admin:
        raise HTTPException(
            status_code=403,
            detail="Acesso permitido apenas para administradores."
        )

    return usuario_db
