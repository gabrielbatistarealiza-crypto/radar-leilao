from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer

from app.database.database import Base


class CaixaDataWorkerState(Base):
    """Estado persistente da coleta automática de datas da CAIXA."""

    __tablename__ = "caixa_data_worker_state"

    id = Column(Integer, primary_key=True, default=1)
    cursor_id = Column(Integer, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    bloqueado_ate = Column(DateTime, nullable=True)
    bloqueios_consecutivos = Column(Integer, nullable=False, default=0)
    atualizado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
