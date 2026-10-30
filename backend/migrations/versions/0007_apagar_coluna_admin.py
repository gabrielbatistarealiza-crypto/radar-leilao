"""apagar coluna admin

Passo B da remoção da coluna antiga "admin" de usuarios. O papel vive só em
`tipo` desde a 0004; a versão anterior da API (passo A) já não lê nem escreve
esta coluna, por isso pode ser apagada com essa versão no ar.

O downgrade volta a criar a coluna e preenche-a a partir do tipo.

Revision ID: 0007
Revises: 0006
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('usuarios', 'admin')


def downgrade() -> None:
    op.add_column('usuarios', sa.Column('admin', sa.Boolean(), nullable=True))
    op.execute("UPDATE usuarios SET admin = (tipo = 'admin')")
