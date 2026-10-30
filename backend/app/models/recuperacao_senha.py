from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database.database import Base


class RecuperacaoSenha(Base):
    """Pedido de recuperação de senha. Guarda só o hash do código enviado por e-mail."""

    __tablename__ = "recuperacoes_senha"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo_hash = Column(String(64), nullable=False, unique=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    expira_em = Column(DateTime, nullable=False)
    usado_em = Column(DateTime, nullable=True)
