import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from jose import jwt


load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY não configurada.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def token_do_usuario(usuario) -> str:
    """Token de sessão: identifica o utilizador pelo id ("sub" e "id"), não pelo e-mail."""
    return criar_token({"sub": str(usuario.id), "id": usuario.id})


def criar_token(dados: dict):
    payload = dados.copy()
    expira_em = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload.update({"exp": expira_em})

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
