from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.database.database import Base


class Notificacao(Base):
    __tablename__ = "notificacoes"
    __table_args__ = (
        UniqueConstraint("usuario_id", "imovel_id", "evento", name="uq_notificacao_usuario_imovel_evento"),
    )

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    imovel_id = Column(Integer, ForeignKey("imoveis.id", ondelete="CASCADE"), nullable=False, index=True)
    evento = Column(String(100), nullable=False)
    tipo = Column(String(30), nullable=False)
    titulo = Column(String(180), nullable=False)
    mensagem = Column(Text, nullable=False)
    lida = Column(Boolean, nullable=False, default=False, index=True)
    criada_em = Column(DateTime, nullable=False, default=datetime.utcnow)
