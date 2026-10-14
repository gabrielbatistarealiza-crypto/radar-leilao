from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text

from app.database.database import Base


class SimulacaoRentabilidade(Base):
    __tablename__ = "simulacoes_rentabilidade"

    id = Column(Integer, primary_key=True, index=True)
    oportunidade_id = Column(
        Integer, ForeignKey("oportunidades.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    nome = Column(String(120), nullable=False)
    preco_aquisicao = Column(Numeric(14, 2), nullable=False)
    impostos_taxas = Column(Numeric(14, 2), nullable=True)
    custos_juridicos = Column(Numeric(14, 2), nullable=True)
    reformas = Column(Numeric(14, 2), nullable=True)
    outras_despesas = Column(Numeric(14, 2), nullable=True)
    valor_revenda = Column(Numeric(14, 2), nullable=False)
    observacoes = Column(Text, nullable=True)
    criado_por_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
