"""execucoes da rotina

Registo de cada execução da rotina da Caixa (tarefa agendada no computador local),
para a API avisar os administradores por e-mail, e o último envio de cada aviso do
sistema. Só acrescenta duas tabelas.

Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0011'
down_revision: Union[str, None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'execucoes_rotina',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('iniciada_em', sa.DateTime(), nullable=True),
        sa.Column('terminada_em', sa.DateTime(), nullable=False),
        sa.Column('codigo_saida', sa.Integer(), nullable=False),
        sa.Column('resumo', sa.Text(), nullable=False),
        sa.Column('avisado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_execucoes_rotina_id'), 'execucoes_rotina', ['id'], unique=False)
    op.create_index(op.f('ix_execucoes_rotina_terminada_em'), 'execucoes_rotina', ['terminada_em'], unique=False)
    op.create_table(
        'avisos_sistema',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=50), nullable=False),
        sa.Column('enviado_em', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tipo'),
    )
    op.create_index(op.f('ix_avisos_sistema_id'), 'avisos_sistema', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_avisos_sistema_id'), table_name='avisos_sistema')
    op.drop_table('avisos_sistema')
    op.drop_index(op.f('ix_execucoes_rotina_terminada_em'), table_name='execucoes_rotina')
    op.drop_index(op.f('ix_execucoes_rotina_id'), table_name='execucoes_rotina')
    op.drop_table('execucoes_rotina')
