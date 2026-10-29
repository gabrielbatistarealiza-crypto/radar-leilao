"""As migrações do Alembic e os modelos têm de descrever sempre o mesmo esquema.

Se alguém mudar um modelo sem criar a migração (ou o contrário), este teste falha.
No SQLite corre por omissão; na CI corre também em PostgreSQL (TEST_DATABASE_URL).
"""
import ast
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import app.models  # noqa: F401
from app.database.database import Base

BACKEND = Path(__file__).resolve().parents[1]


def configuracao(conexao=None):
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    if conexao is not None:
        cfg.attributes["connection"] = conexao
    return cfg


def test_todos_os_modelos_estao_registados_em_app_models():
    pasta = BACKEND / "app" / "models"
    arvore = ast.parse((pasta / "__init__.py").read_text(encoding="utf-8"))
    importados = {
        no.module.rsplit(".", 1)[-1]
        for no in ast.walk(arvore)
        if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("app.models.")
    }
    ficheiros = {p.stem for p in pasta.glob("*.py") if p.stem != "__init__"}
    assert ficheiros - importados == set(), "importe estes modelos em app/models/__init__.py"


def test_ha_uma_so_cabeca_de_migracoes():
    assert len(ScriptDirectory.from_config(configuracao()).get_heads()) == 1


def test_migracoes_criam_exatamente_o_esquema_dos_modelos(motor):
    Base.metadata.drop_all(motor)
    with motor.begin() as conexao:
        conexao.execute(text("DROP TABLE IF EXISTS alembic_version"))
    try:
        with motor.begin() as conexao:
            command.upgrade(configuracao(conexao), "head")

        with motor.connect() as conexao:
            contexto = MigrationContext.configure(conexao, opts={"compare_type": True})
            diferencas = compare_metadata(contexto, Base.metadata)
            assert diferencas == [], diferencas
            assert set(Base.metadata.tables) <= set(inspect(conexao).get_table_names())

        with motor.begin() as conexao:
            command.downgrade(configuracao(conexao), "base")
        with motor.connect() as conexao:
            assert set(inspect(conexao).get_table_names()) <= {"alembic_version"}
    finally:
        with motor.begin() as conexao:
            conexao.execute(text("DROP TABLE IF EXISTS alembic_version"))
