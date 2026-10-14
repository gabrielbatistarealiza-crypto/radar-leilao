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

from app.database.database import Base


class Negociacao(Base):
    __tablename__ = "negociacoes"

    id = Column(Integer, primary_key=True, index=True)

    oportunidade_id = Column(
        Integer,
        ForeignKey("oportunidades.id"),
        nullable=False,
        index=True,
    )

    status = Column(
        String(30),
        nullable=False,
        default="aberta",
        index=True,
    )

    valor_proposto = Column(
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