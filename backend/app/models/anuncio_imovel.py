from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database.database import Base


class AnuncioImovel(Base):
    __tablename__ = "anuncios_imoveis"

    id = Column(Integer, primary_key=True, index=True)

    corretor_id = Column(
        Integer,
        ForeignKey("corretores.id"),
        nullable=False,
        index=True,
    )

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
        default="publicado",
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