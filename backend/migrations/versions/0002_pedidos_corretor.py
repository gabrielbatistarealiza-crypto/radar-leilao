"""pedidos corretor

Tabela dos pedidos de conta de corretor (registo público).

Enquanto o arranque da API ainda usa create_all (até à fase 2 do
docs/PLANO_REFACAO.md), a produção pode já ter esta tabela quando a migração
correr: nesse caso não faz nada e só avança a versão.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29 16:38:39.274296
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("pedidos_corretor"):
        return  # já criada pelo create_all do arranque

    op.create_table('pedidos_corretor',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('creci', sa.String(length=50), nullable=False),
    sa.Column('nome_profissional', sa.String(length=150), nullable=True),
    sa.Column('telefone', sa.String(length=30), nullable=True),
    sa.Column('imobiliaria', sa.String(length=150), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('motivo', sa.String(length=500), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.Column('decidido_em', sa.DateTime(), nullable=True),
    sa.Column('decidido_por', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['decidido_por'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pedidos_corretor_creci'), 'pedidos_corretor', ['creci'], unique=False)
    op.create_index(op.f('ix_pedidos_corretor_id'), 'pedidos_corretor', ['id'], unique=False)
    op.create_index(op.f('ix_pedidos_corretor_status'), 'pedidos_corretor', ['status'], unique=False)
    op.create_index(op.f('ix_pedidos_corretor_usuario_id'), 'pedidos_corretor', ['usuario_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pedidos_corretor_usuario_id'), table_name='pedidos_corretor')
    op.drop_index(op.f('ix_pedidos_corretor_status'), table_name='pedidos_corretor')
    op.drop_index(op.f('ix_pedidos_corretor_id'), table_name='pedidos_corretor')
    op.drop_index(op.f('ix_pedidos_corretor_creci'), table_name='pedidos_corretor')
    op.drop_table('pedidos_corretor')
