"""Porteiro único para tudo o que contacta o site da CAIXA.

Qualquer rotina (datas, fotos, importação, endpoints manuais) entra por
`acesso_caixa`, que:

1. adquire o lock do processo (CAIXA_COLETA_LOCK);
2. em PostgreSQL, adquire também um lock consultivo numa ligação própria,
   para que dois processos (reload, várias instâncias) não consultem a CAIXA
   ao mesmo tempo;
3. recusa enquanto houver uma espera de bloqueio em vigor (bloqueado_ate);
4. liberta tudo no fim, mesmo com exceção.

`registrar_bloqueio_caixa` é o único sítio que grava a espera após um
bloqueio/CAPTCHA. Depois de um bloqueio, quem chamou deve parar, não insistir.
"""
import logging
import os
from contextlib import contextmanager
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import text

from app.models.caixa_data_worker_state import CaixaDataWorkerState
from app.services.caixa_datas_worker import _obter_estado, registrar_bloqueio
from app.services.caixa_worker_lock import CAIXA_COLETA_LOCK

logger = logging.getLogger(__name__)

# Identificador do lock consultivo PostgreSQL (diferente do das notificações).
LOCK_CONSULTIVO_CAIXA = 74_202_310


class CaixaOcupada(Exception):
    """Outra rotina (deste ou de outro processo) já está a consultar a CAIXA."""


class CaixaEmEspera(Exception):
    """Há uma espera de bloqueio em vigor: não se consulta a CAIXA."""

    def __init__(self, bloqueado_ate: datetime, agora: datetime):
        self.bloqueado_ate = bloqueado_ate
        self.segundos_restantes = max(0, int((bloqueado_ate - agora).total_seconds()))
        super().__init__(
            f"Espera de bloqueio da CAIXA até {bloqueado_ate.isoformat()}"
        )


def ler_espera_em_vigor(db, agora: datetime | None = None) -> datetime | None:
    """Devolve bloqueado_ate se ainda estiver no futuro, lido da base de dados."""
    agora = agora or datetime.utcnow()
    estado = (
        db.query(CaixaDataWorkerState)
        .populate_existing()
        .filter(CaixaDataWorkerState.id == 1)
        .first()
    )
    if estado and estado.bloqueado_ate and estado.bloqueado_ate > agora:
        return estado.bloqueado_ate
    return None


def _adquirir_lock_entre_processos(db):
    """Lock consultivo PostgreSQL numa ligação dedicada; None noutros bancos."""
    motor = db.get_bind()
    if motor.dialect.name != "postgresql":
        return None
    ligacao = motor.connect()
    try:
        obtido = bool(
            ligacao.execute(
                text("SELECT pg_try_advisory_lock(:id)"),
                {"id": LOCK_CONSULTIVO_CAIXA},
            ).scalar()
        )
        # O lock é de sessão: sobrevive ao commit; não deixa transação aberta.
        ligacao.commit()
    except Exception:
        ligacao.close()
        raise
    if not obtido:
        ligacao.close()
        raise CaixaOcupada("Outro processo está a consultar a CAIXA.")
    return ligacao


def _libertar_lock_entre_processos(ligacao) -> None:
    if ligacao is None:
        return
    try:
        ligacao.execute(
            text("SELECT pg_advisory_unlock(:id)"),
            {"id": LOCK_CONSULTIVO_CAIXA},
        )
        ligacao.commit()
    except Exception:
        logger.exception("Falha ao libertar o lock consultivo da CAIXA.")
    finally:
        # Fechar a ligação também liberta o lock de sessão.
        ligacao.close()


@contextmanager
def acesso_caixa(db, origem: str, esperar: bool = True):
    """Autoriza uma consulta à CAIXA ou levanta CaixaOcupada/CaixaEmEspera.

    `esperar=True` espera pelo lock deste processo (rotinas automáticas);
    `esperar=False` recusa logo (endpoints HTTP, para não prender threads).
    O lock entre processos nunca espera.
    """
    if not CAIXA_COLETA_LOCK.acquire(blocking=esperar):
        raise CaixaOcupada("Outra rotina deste processo está a consultar a CAIXA.")
    ligacao = None
    try:
        ligacao = _adquirir_lock_entre_processos(db)
        agora = datetime.utcnow()
        bloqueado_ate = ler_espera_em_vigor(db, agora)
        if bloqueado_ate:
            raise CaixaEmEspera(bloqueado_ate, agora)
        logger.debug("Acesso à CAIXA autorizado para %s.", origem)
        yield
    finally:
        _libertar_lock_entre_processos(ligacao)
        CAIXA_COLETA_LOCK.release()


@contextmanager
def acesso_caixa_http(db, origem: str):
    """Versão para endpoints: 409 se ocupado, 429 se em espera."""
    try:
        with acesso_caixa(db, origem, esperar=False):
            yield
    except CaixaOcupada as erro:
        raise HTTPException(
            status_code=409,
            detail="Já existe uma consulta à CAIXA em curso. Tente mais tarde.",
        ) from erro
    except CaixaEmEspera as erro:
        raise HTTPException(
            status_code=429,
            detail=(
                "A CAIXA bloqueou temporariamente as consultas. "
                f"A retomada está prevista para {erro.bloqueado_ate.isoformat()}."
            ),
        ) from erro


def registrar_bloqueio_caixa(db, origem: str, agora: datetime | None = None) -> int:
    """Grava a espera progressiva (12h, 24h, 48h, 72h) e faz commit.

    Cria a linha de estado se ainda não existir (evita o antigo None += 1).
    Devolve as horas de espera.
    """
    agora = agora or datetime.utcnow()
    estado = _obter_estado(db)
    horas = registrar_bloqueio(estado, agora)
    db.commit()
    logger.warning(
        "CAIXA bloqueou o acesso (%s). Novas consultas suspensas por %s horas.",
        origem,
        horas,
    )
    return horas


INTERVALO_FOTOS_PADRAO_SEGUNDOS = 30
INTERVALO_FOTOS_MINIMO_SEGUNDOS = 5


def intervalo_entre_fotos() -> int:
    """Pausa entre dois imóveis consultados para fotos (worker e endpoints)."""
    return intervalo_env(
        "RADAR_CAIXA_FOTOS_INTERVALO_SEGUNDOS",
        INTERVALO_FOTOS_PADRAO_SEGUNDOS,
        INTERVALO_FOTOS_MINIMO_SEGUNDOS,
    )


def intervalo_env(nome: str, padrao: int, minimo: int) -> int:
    """Lê um intervalo em segundos de uma variável de ambiente."""
    valor = os.getenv(nome, "").strip()
    if not valor:
        return padrao
    try:
        segundos = int(float(valor))
    except ValueError:
        logger.warning("%s inválido (%r); a usar %s s.", nome, valor, padrao)
        return padrao
    return max(minimo, segundos)
