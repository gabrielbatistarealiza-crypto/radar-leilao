"""Arranque com migrações (app/migrar.py): base vazia, base marcada e base sem versão."""
import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app import migrar
from app.database.database import Base


def motor_vazio():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def versao(motor):
    with motor.connect() as conexao:
        return conexao.execute(text("select version_num from alembic_version")).scalar()


def cabeca():
    return ScriptDirectory.from_config(migrar.configuracao()).get_current_head()


def test_base_vazia_fica_com_todas_as_tabelas_e_na_ultima_versao():
    motor = motor_vazio()
    migrar.preparar_base(motor)

    assert versao(motor) == cabeca()
    assert set(Base.metadata.tables) <= set(inspect(motor).get_table_names())


def test_base_com_tabelas_mas_sem_versao_e_recusada_sem_mexer(motor):
    # O fixture "motor" cria as tabelas com create_all, como a produção antes da marcação.
    with pytest.raises(migrar.BaseSemVersao):
        migrar.preparar_base(motor)

    assert not inspect(motor).has_table("alembic_version")


def test_base_marcada_numa_versao_antiga_avanca_ate_a_ultima():
    motor = motor_vazio()
    with motor.begin() as conexao:
        command.upgrade(migrar.configuracao(conexao), "0001")
    assert versao(motor) == "0001"

    migrar.preparar_base(motor)

    assert versao(motor) == cabeca()
    assert inspect(motor).has_table("pedidos_corretor")


def test_correr_duas_vezes_nao_faz_nada_a_segunda():
    motor = motor_vazio()
    migrar.preparar_base(motor)
    migrar.preparar_base(motor)
    assert versao(motor) == cabeca()
