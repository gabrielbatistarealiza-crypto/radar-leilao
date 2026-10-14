from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database.database import Base


class AtividadeOportunidade(Base):
    __tablename__ = "atividades_oportunidade"

    id = Column(Integer, primary_key=True, index=True)
    oportunidade_id = Column(
        Integer,
        ForeignKey("oportunidades.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo = Column(String(20), nullable=False, index=True)
    canal = Column(String(40), nullable=True)
    descricao = Column(Text, nullable=False)
    status_anterior = Column(String(30), nullable=True)
    status_novo = Column(String(30), nullable=True)
    criado_por_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
