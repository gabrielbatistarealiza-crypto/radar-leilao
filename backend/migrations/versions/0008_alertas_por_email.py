"""alertas por email

Resumo diário dos alertas por e-mail: preferência e data do último resumo em
usuarios; data de envio em notificacoes. Só acrescenta colunas (a preferência
nasce ligada para todos).

Revision ID: 0008
Revises: 0007
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('usuarios', sa.Column('alertas_por_email', sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column('usuarios', sa.Column('ultimo_resumo_email_em', sa.DateTime(), nullable=True))
    op.add_column('notificacoes', sa.Column('enviada_por_email_em', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('notificacoes', 'enviada_por_email_em')
    op.drop_column('usuarios', 'ultimo_resumo_email_em')
    op.drop_column('usuarios', 'alertas_por_email')
