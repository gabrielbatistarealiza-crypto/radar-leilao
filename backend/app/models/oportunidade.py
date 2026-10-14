from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database.database import Base


class Oportunidade(Base):
    __tablename__ = "oportunidades"

    id = Column(Integer, primary_key=True, index=True)

    imovel_id = Column(
        Integer,
        ForeignKey("imoveis.id"),
        nullable=True,
        index=True,
    )

    anuncio_id = Column(
        Integer,
        ForeignKey("anuncios_imoveis.id"),
        nullable=True,
        index=True,
    )

    cliente_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False,
        index=True,
    )

    corretor_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=True,
        index=True,
    )

    status = Column(
        String(30),
        nullable=False,
        default="interesse",
        index=True,
    )

    valor_imovel = Column(
        Numeric(14, 2),
        nullable=True,
    )

    observacoes = Column(
        Text,
        nullable=True,
    )

    criado_em = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    atualizado_em = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    imovel = relationship(
        "Imovel",
        back_populates="oportunidades",
    )

    anuncio = relationship(
        "AnuncioImovel",
        foreign_keys=[anuncio_id],
    )

    cliente = relationship(
        "Usuario",
        foreign_keys=[cliente_id],
    )

    corretor = relationship(
        "Usuario",
        foreign_keys=[corretor_id],
    )