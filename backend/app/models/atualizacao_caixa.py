from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text

from app.database.database import Base


class AtualizacaoCaixa(Base):
    __tablename__ = "atualizacoes_caixa"

    id = Column(Integer, primary_key=True, index=True)

    iniciada_em = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    concluida_em = Column(
        DateTime,
        nullable=True,
    )

    status = Column(
        String(30),
        nullable=False,
        default="EXECUTANDO",
    )

    imoveis_atualizados = Column(
        Integer,
        nullable=False,
        default=0,
    )

    imoveis_removidos = Column(
        Integer,
        nullable=False,
        default=0,
    )

    fotos_pendentes = Column(
        Integer,
        nullable=False,
        default=0,
    )

    estados_baixados = Column(
        Integer,
        nullable=False,
        default=0,
    )

    erro = Column(
        Text,
        nullable=True,
    )
