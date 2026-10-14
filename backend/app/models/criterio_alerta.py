from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String

from app.database.database import Base


class CriterioAlerta(Base):
    __tablename__ = "criterios_alerta"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    nome = Column(String(120), nullable=False)
    desconto_minimo = Column(Numeric(6, 2), nullable=True)
    preco_maximo = Column(Numeric(14, 2), nullable=True)
    estado = Column(String(2), nullable=True)
    cidade = Column(String(100), nullable=True)
    roi_minimo = Column(Numeric(7, 2), nullable=True)
    simulacao_id = Column(Integer, ForeignKey("simulacoes_rentabilidade.id", ondelete="SET NULL"), nullable=True)
    alertar_prazos_dias = Column(Integer, nullable=False, default=7)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
