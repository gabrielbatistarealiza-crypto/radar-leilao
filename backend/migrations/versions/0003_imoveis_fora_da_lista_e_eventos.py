"""imoveis fora da lista e eventos

Os imóveis da Caixa deixam de ser apagados quando saem da lista: ficam com
na_lista=false (todos começam em true) e o histórico vai para imovel_eventos.
Só acrescenta; não altera nem apaga dados existentes.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30 00:00:50.015480
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('imovel_eventos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('imovel_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=30), nullable=False),
    sa.Column('momento', sa.DateTime(), nullable=False),
    sa.Column('valor_anterior', sa.Float(), nullable=True),
    sa.Column('valor_novo', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['imovel_id'], ['imoveis.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_imovel_eventos_id'), 'imovel_eventos', ['id'], unique=False)
    op.create_index(op.f('ix_imovel_eventos_imovel_id'), 'imovel_eventos', ['imovel_id'], unique=False)
    op.add_column('imoveis', sa.Column('na_lista', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('imoveis', sa.Column('saiu_da_lista_em', sa.DateTime(), nullable=True))
    op.add_column('imoveis', sa.Column('visto_na_lista_em', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('imoveis', 'visto_na_lista_em')
    op.drop_column('imoveis', 'saiu_da_lista_em')
    op.drop_column('imoveis', 'na_lista')
    op.drop_index(op.f('ix_imovel_eventos_imovel_id'), table_name='imovel_eventos')
    op.drop_index(op.f('ix_imovel_eventos_id'), table_name='imovel_eventos')
    op.drop_table('imovel_eventos')
