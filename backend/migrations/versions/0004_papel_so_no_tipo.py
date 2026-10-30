"""papel só no tipo

Fase 4: o papel do utilizador passa a viver só em usuarios.tipo. Quem tinha
admin = true fica com tipo = 'admin' e a coluna antiga "admin" é acertada com o
tipo. Não altera o esquema: a coluna "admin" fica (a versão anterior da API ainda
a lê durante o deploy) e só sai numa migração futura.

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE usuarios SET tipo = 'admin' WHERE admin IS TRUE AND tipo <> 'admin'")
    op.execute("UPDATE usuarios SET admin = (tipo = 'admin')")


def downgrade() -> None:
    # Os dados ficam coerentes nos dois sentidos; nada a desfazer.
    pass
