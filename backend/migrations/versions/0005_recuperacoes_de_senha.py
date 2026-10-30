"""recuperacoes de senha

Fase 4B: pedidos de recuperação de senha (só o hash do código enviado por
e-mail, validade e uso). Só acrescenta uma tabela.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-30 17:28:18.345220
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('recuperacoes_senha',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('codigo_hash', sa.String(length=64), nullable=False),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.Column('expira_em', sa.DateTime(), nullable=False),
    sa.Column('usado_em', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo_hash')
    )
    op.create_index(op.f('ix_recuperacoes_senha_id'), 'recuperacoes_senha', ['id'], unique=False)
    op.create_index(op.f('ix_recuperacoes_senha_usuario_id'), 'recuperacoes_senha', ['usuario_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_recuperacoes_senha_usuario_id'), table_name='recuperacoes_senha')
    op.drop_index(op.f('ix_recuperacoes_senha_id'), table_name='recuperacoes_senha')
    op.drop_table('recuperacoes_senha')
