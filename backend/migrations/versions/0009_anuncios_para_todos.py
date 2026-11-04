"""anuncios para todos

Qualquer conta pode publicar anúncios: o anúncio passa a pertencer a um
utilizador (usuario_id). Os existentes ficam com o dono do perfil de corretor.
O perfil de corretor deixa de ser obrigatório. Acrescenta a comissão aceite (6%
do valor de venda, paga pelo vendedor) e o motivo de rejeição da moderação.

Revision ID: 0009
Revises: 0008
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('anuncios_imoveis', sa.Column('usuario_id', sa.Integer(), nullable=True))
    op.add_column('anuncios_imoveis', sa.Column('comissao_percentual', sa.Numeric(5, 2), nullable=True))
    op.add_column('anuncios_imoveis', sa.Column('comissao_aceite_em', sa.DateTime(), nullable=True))
    op.add_column('anuncios_imoveis', sa.Column('motivo_rejeicao', sa.String(length=500), nullable=True))
    # Os anúncios que já existem pertencem ao utilizador do perfil de corretor.
    op.execute(
        "UPDATE anuncios_imoveis SET usuario_id = "
        "(SELECT c.usuario_id FROM corretores c WHERE c.id = anuncios_imoveis.corretor_id)"
    )
    with op.batch_alter_table('anuncios_imoveis') as tabela:
        tabela.alter_column('usuario_id', existing_type=sa.Integer(), nullable=False)
        tabela.alter_column('corretor_id', existing_type=sa.Integer(), nullable=True)
        tabela.create_foreign_key('fk_anuncios_imoveis_usuario_id', 'usuarios', ['usuario_id'], ['id'])
        tabela.create_index('ix_anuncios_imoveis_usuario_id', ['usuario_id'], unique=False)


def downgrade() -> None:
    # Anúncios sem perfil de corretor não cabem no esquema antigo: são apagados.
    op.execute("DELETE FROM anuncio_imagens WHERE anuncio_id IN "
               "(SELECT id FROM anuncios_imoveis WHERE corretor_id IS NULL)")
    op.execute("UPDATE oportunidades SET anuncio_id = NULL WHERE anuncio_id IN "
               "(SELECT id FROM anuncios_imoveis WHERE corretor_id IS NULL)")
    op.execute("DELETE FROM anuncios_imoveis WHERE corretor_id IS NULL")
    with op.batch_alter_table('anuncios_imoveis') as tabela:
        tabela.drop_index('ix_anuncios_imoveis_usuario_id')
        tabela.drop_constraint('fk_anuncios_imoveis_usuario_id', type_='foreignkey')
        tabela.alter_column('corretor_id', existing_type=sa.Integer(), nullable=False)
        tabela.drop_column('motivo_rejeicao')
        tabela.drop_column('comissao_aceite_em')
        tabela.drop_column('comissao_percentual')
        tabela.drop_column('usuario_id')
