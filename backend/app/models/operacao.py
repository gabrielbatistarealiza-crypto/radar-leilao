from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)

from app.database.database import Base


class Operacao(Base):
    __tablename__ = "operacoes"

    id = Column(Integer, primary_key=True, index=True)

    oportunidade_id = Column(
        Integer,
        ForeignKey("oportunidades.id"),
        nullable=False,
        index=True,
    )

    valor_imovel = Column(
        Numeric(14, 2),
        nullable=False,
    )

    percentual_taxa = Column(
        Numeric(5, 2),
        nullable=False,
        default=10.00,
    )

    valor_taxa = Column(
        Numeric(14, 2),
        nullable=False,
    )

    status = Column(
        String(30),
        nullable=False,
        default="em_andamento",
        index=True,
    )

    criado_em = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    concluido_em = Column(
        DateTime,
        nullable=True,
    )