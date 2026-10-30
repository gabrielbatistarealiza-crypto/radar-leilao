import logging
import math
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.usuario import Usuario
from app.schemas.login import Login
from app.security.password import verificar_senha
from app.security.token import token_do_usuario

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Login"]
)

# Tentativas falhadas permitidas por e-mail dentro da janela, antes de bloquear.
TENTATIVAS_FALHADAS_MAX = 5
JANELA_TENTATIVAS_SEGUNDOS = 15 * 60


class LimiteTentativasLogin:
    """Conta tentativas falhadas de login por e-mail, em memória.

    A chave é o e-mail e não o IP: atrás do proxy do Render a API recebe sempre
    o IP interno do proxy. Contas separadas por processo; a API corre com um só
    worker (ver o Dockerfile).
    """

    def __init__(
        self,
        maximo: int = TENTATIVAS_FALHADAS_MAX,
        janela: int = JANELA_TENTATIVAS_SEGUNDOS,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.maximo = maximo
        self.janela = janela
        self.relogio = relogio
        self._falhas: dict[str, deque[float]] = defaultdict(deque)

    def _recentes(self, chave: str) -> deque[float]:
        agora = self.relogio()
        fila = self._falhas[chave]
        while fila and agora - fila[0] >= self.janela:
            fila.popleft()
        if not fila:
            self._falhas.pop(chave, None)
            return deque()
        return fila

    def segundos_de_bloqueio(self, chave: str) -> int:
        """0 se pode tentar; senão, os segundos até a falha mais antiga sair da janela."""
        fila = self._recentes(chave)
        if len(fila) < self.maximo:
            return 0
        return max(1, math.ceil(self.janela - (self.relogio() - fila[0])))

    def registar_falha(self, chave: str) -> None:
        self._recentes(chave)
        self._falhas[chave].append(self.relogio())

    def limpar(self, chave: str) -> None:
        self._falhas.pop(chave, None)

    def limpar_tudo(self) -> None:
        self._falhas.clear()


limite_login = LimiteTentativasLogin()


def _chave(email: str) -> str:
    return email.strip().lower()


def _procurar_usuario(db: Session, email: str, chave: str) -> Usuario | None:
    """Procura a conta do e-mail sem distinguir maiúsculas, como o contador.

    Primeiro o e-mail exatamente como foi escrito; senão, sem distinguir
    maiúsculas, mas só se houver uma única conta. Se duas contas diferirem
    apenas nas maiúsculas, só o e-mail exato entra.
    """
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario:
        return usuario
    candidatos = (
        db.query(Usuario)
        .filter(func.lower(Usuario.email) == chave)
        .limit(2)
        .all()
    )
    return candidatos[0] if len(candidatos) == 1 else None


@router.post("/login")
def login(dados: Login, db: Session = Depends(get_db)):
    chave = _chave(dados.email)

    # A mesma resposta exista ou não o e-mail, para não revelar contas.
    espera = limite_login.segundos_de_bloqueio(chave)
    if espera:
        logger.warning("Login bloqueado temporariamente após tentativas falhadas.")
        raise HTTPException(
            status_code=429,
            detail="Demasiadas tentativas falhadas. Tente de novo mais tarde.",
            headers={"Retry-After": str(espera)},
        )

    usuario = _procurar_usuario(db, dados.email, chave)

    if not usuario or not verificar_senha(dados.senha, usuario.senha):
        limite_login.registar_falha(chave)
        raise HTTPException(
            status_code=401,
            detail="E-mail ou senha invalidos."
        )

    limite_login.limpar(chave)

    token = token_do_usuario(usuario)

    return {
        "access_token": token,
        "token_type": "bearer"
    }
