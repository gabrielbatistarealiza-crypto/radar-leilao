"""Ambiente do Alembic: usa os modelos da app e a DATABASE_URL do ambiente."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (regista todas as tabelas)
from app.database.database import DATABASE_URL, Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    # Permite a quem chama (por exemplo os testes) passar outra ligação.
    return config.attributes.get("url") or DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    conexao = config.attributes.get("connection")
    if conexao is not None:
        _correr(conexao)
        return
    motor = create_engine(_url(), poolclass=pool.NullPool)
    with motor.connect() as conexao:
        _correr(conexao)


def _correr(conexao) -> None:
    context.configure(
        connection=conexao,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=conexao.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
