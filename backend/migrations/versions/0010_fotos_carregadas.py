"""fotos carregadas

Fotos dos anúncios escolhidas no computador ou no telemóvel: ficam na própria base
(reduzidas no aparelho antes do envio). Só acrescenta colunas a anuncio_imagens.

Revision ID: 0010
Revises: 0009
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('anuncio_imagens', sa.Column('chave', sa.String(length=32), nullable=True))
    op.add_column('anuncio_imagens', sa.Column('tipo_mime', sa.String(length=30), nullable=True))
    op.add_column('anuncio_imagens', sa.Column('tamanho', sa.Integer(), nullable=True))
    op.add_column('anuncio_imagens', sa.Column('conteudo', sa.LargeBinary(), nullable=True))
    op.create_index(op.f('ix_anuncio_imagens_chave'), 'anuncio_imagens', ['chave'], unique=True)


def downgrade() -> None:
    # As fotos carregadas só existem nestas colunas: saem com elas.
    op.execute("DELETE FROM anuncio_imagens WHERE chave IS NOT NULL")
    op.drop_index(op.f('ix_anuncio_imagens_chave'), table_name='anuncio_imagens')
    op.drop_column('anuncio_imagens', 'conteudo')
    op.drop_column('anuncio_imagens', 'tamanho')
    op.drop_column('anuncio_imagens', 'tipo_mime')
    op.drop_column('anuncio_imagens', 'chave')
