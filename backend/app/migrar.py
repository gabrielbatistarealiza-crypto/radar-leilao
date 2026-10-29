"""Aplica as migrações do Alembic antes de a API arrancar.

No Dockerfile: `python -m app.migrar && uvicorn app.main:app ...`. Se falhar, a
API não arranca e o Render mantém a versão anterior no ar.

Recusa uma base que já tem tabelas mas não tem versão do Alembic: seria a
produção antes da marcação única (backend/migrations/producao/marcar_0001_*),
e correr a 0001 por cima das tabelas existentes falharia a meio.
"""
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

BACKEND = Path(__file__).resolve().parents[1]
logger = logging.getLogger("app.migrar")


class BaseSemVersao(RuntimeError):
    pass


def configuracao(conexao=None) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    if conexao is not None:
        cfg.attributes["connection"] = conexao
    return cfg


def preparar_base(motor) -> None:
    with motor.connect() as conexao:
        inspetor = inspect(conexao)
        tem_tabelas = inspetor.has_table("imoveis")
        tem_versao = inspetor.has_table("alembic_version")
    if tem_tabelas and not tem_versao:
        raise BaseSemVersao(
            "A base já tem tabelas mas não tem versão do Alembic. Marque-a uma vez "
            "com backend/migrations/producao/marcar_0001_COMMIT.sql antes deste deploy."
        )
    with motor.begin() as conexao:
        command.upgrade(configuracao(conexao), "head")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
    from app.database.database import engine

    try:
        preparar_base(engine)
    except BaseSemVersao as erro:
        logger.error("%s", erro)
        return 1
    logger.info("Migrações aplicadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
