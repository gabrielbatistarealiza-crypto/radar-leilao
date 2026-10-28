from sqlalchemy import Column, Date, Integer

from app.database.database import Base


class CaixaPedidosDia(Base):
    """Pedidos de datas feitos à CAIXA em cada dia (UTC), para o limite diário.

    Cada pedido é contado (com commit) ANTES de ser feito: um processo que
    morra a meio nunca fica com pedidos por contar.
    """

    __tablename__ = "caixa_pedidos_dia"

    dia = Column(Date, primary_key=True)
    pedidos = Column(Integer, nullable=False, default=0)
