"""Execuções da rotina da Caixa (tarefa agendada no computador local) e avisos do sistema.

A rotina corre no computador do administrador (a Caixa bloqueia o IP do Render) e, no
fim, grava aqui o que aconteceu. A API, que tem o envio de e-mails, avisa os
administradores de cada execução e quando passam dias sem nenhuma.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database.database import Base


class ExecucaoRotina(Base):
    __tablename__ = "execucoes_rotina"

    id = Column(Integer, primary_key=True, index=True)
    iniciada_em = Column(DateTime, nullable=True)
    terminada_em = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    # 0 normal, 2 parou (paragem manual, bloqueio), 3 VPN, 5 fora do horário, outro = erro.
    codigo_saida = Column(Integer, nullable=False, default=0)
    resumo = Column(Text, nullable=False, default="{}")  # JSON
    avisado_em = Column(DateTime, nullable=True)


class AvisoSistema(Base):
    """Último envio de cada tipo de aviso (para não repetir o mesmo aviso a toda a hora)."""

    __tablename__ = "avisos_sistema"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(50), nullable=False, unique=True)
    enviado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
