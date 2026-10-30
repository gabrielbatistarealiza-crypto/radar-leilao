"""valores dos leiloes

Valores de venda do 1.º e 2.º leilão lidos do edital (Anexo II). A lista da
Caixa só traz um preço, que nos leilões SFI é igual à avaliação. Só acrescenta
duas colunas que aceitam vazio; nenhum dado existente muda.

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('imoveis', sa.Column('valor_primeiro_leilao', sa.Float(), nullable=True))
    op.add_column('imoveis', sa.Column('valor_segundo_leilao', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('imoveis', 'valor_segundo_leilao')
    op.drop_column('imoveis', 'valor_primeiro_leilao')
