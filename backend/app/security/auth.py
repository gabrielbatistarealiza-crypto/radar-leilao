from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.usuario import Usuario
from app.security.token import SECRET_KEY, ALGORITHM


security = HTTPBearer(auto_error=False)


def usuario_logado(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Autenticação necessária.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _decodificar_token(credentials.credentials)


def _decodificar_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _usuario_do_payload(payload, db: Session):
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token inválido.")

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")
    return usuario


def usuario_atual(
    payload=Depends(usuario_logado),
    db: Session = Depends(get_db),
):
    return _usuario_do_payload(payload, db)


def usuario_opcional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    """Resolve o usuário quando há Bearer token; permite chamadas anônimas."""
    if credentials is None:
        return None
    return _usuario_do_payload(_decodificar_token(credentials.credentials), db)


def usuario_e_admin(usuario: Usuario) -> bool:
    return bool(usuario.admin) or getattr(usuario, "tipo", None) == "admin"


def usuario_e_corretor(usuario: Usuario) -> bool:
    return getattr(usuario, "tipo", None) == "corretor"


def usuario_admin(usuario: Usuario = Depends(usuario_atual)):
    if not usuario_e_admin(usuario):
        raise HTTPException(
            status_code=403,
            detail="Acesso permitido apenas para administradores.",
        )
    return usuario


def usuario_corretor(usuario: Usuario = Depends(usuario_atual)):
    if not usuario_e_admin(usuario) and not usuario_e_corretor(usuario):
        raise HTTPException(
            status_code=403,
            detail="Acesso permitido apenas para corretores.",
        )
    return usuario


def exigir_acesso_oportunidade(
    usuario: Usuario,
    oportunidade,
    *,
    permitir_cliente: bool = True,
    permitir_corretor: bool = True,
):
    if usuario_e_admin(usuario):
        return

    if (
        permitir_cliente
        and getattr(usuario, "tipo", None) == "cliente"
        and oportunidade.cliente_id == usuario.id
    ):
        return

    if (
        permitir_corretor
        and usuario_e_corretor(usuario)
        and oportunidade.corretor_id == usuario.id
    ):
        return

    raise HTTPException(
        status_code=403,
        detail="Você não tem permissão para acessar este recurso.",
    )
