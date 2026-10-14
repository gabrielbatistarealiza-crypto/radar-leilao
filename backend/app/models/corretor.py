from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.database.database import Base


class Corretor(Base):
    __tablename__ = "corretores"

    id = Column(Integer, primary_key=True, index=True)

    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    nome_profissional = Column(String(150), nullable=True)
    creci = Column(String(50), nullable=False, unique=True, index=True)
    telefone = Column(String(30), nullable=True)
    imobiliaria = Column(String(150), nullable=True)

    ativo = Column(Boolean, nullable=False, default=True)

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