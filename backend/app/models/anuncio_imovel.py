from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database.database import Base

# Estados de um anúncio. Os novos começam em análise até um administrador aprovar.
EM_ANALISE = "em_analise"
PUBLICADO = "publicado"
REJEITADO = "rejeitado"

# Comissão do site, paga pelo vendedor sobre o valor de venda se o negócio fechar pelo site.
COMISSAO_SITE_PERCENTUAL = 6


class AnuncioImovel(Base):
    __tablename__ = "anuncios_imoveis"

    id = Column(Integer, primary_key=True, index=True)

    # Dono do anúncio: qualquer conta pode publicar.
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False,
        index=True,
    )

    # Perfil de corretor, quando quem publica é corretor (senão vazio).
    corretor_id = Column(
        Integer,
        ForeignKey("corretores.id"),
        nullable=True,
        index=True,
    )

    # Comissão aceite por quem publicou (percentagem e quando aceitou).
    comissao_percentual = Column(Numeric(5, 2), nullable=True)
    comissao_aceite_em = Column(DateTime, nullable=True)
    motivo_rejeicao = Column(String(500), nullable=True)

    titulo = Column(String(255), nullable=False)
    tipo = Column(String(100), nullable=True)

    endereco = Column(String(255), nullable=True)
    cidade = Column(String(100), nullable=True)
    estado = Column(String(2), nullable=True)

    valor_mercado = Column(Float, nullable=False)
    valor_anunciado = Column(Float, nullable=False)
    desconto = Column(Float, nullable=False)

    area = Column(Float, nullable=True)
    quartos = Column(Integer, nullable=True)
    banheiros = Column(Integer, nullable=True)
    vagas = Column(Integer, nullable=True)

    descricao = Column(Text, nullable=True)

    status = Column(
        String(30),
        nullable=False,
        default=EM_ANALISE,
        index=True,
    )

    ativo = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    criado_em = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    fotos = relationship(
    "AnuncioImagem",
    back_populates="anuncio",
    cascade="all, delete-orphan",
    order_by="AnuncioImagem.ordem",
)