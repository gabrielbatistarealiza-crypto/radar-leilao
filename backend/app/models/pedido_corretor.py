from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database.database import Base


class PedidoCorretor(Base):
    """Pedido de conta de corretor, à espera da decisão de um administrador.

    Enquanto o pedido está PENDENTE o utilizador continua a ser "cliente":
    só a aprovação muda o tipo para "corretor" e cria o perfil (CRECI).
    """

    __tablename__ = "pedidos_corretor"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    creci = Column(String(50), nullable=False, index=True)
    nome_profissional = Column(String(150), nullable=True)
    telefone = Column(String(30), nullable=True)
    imobiliaria = Column(String(150), nullable=True)

    # PENDENTE, APROVADO ou REJEITADO
    status = Column(String(20), nullable=False, default="PENDENTE", index=True)
    motivo = Column(String(500), nullable=True)

    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    decidido_em = Column(DateTime, nullable=True)
    decidido_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
