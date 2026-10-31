from sqlalchemy import Boolean, Column, DateTime, Integer, String, true
from sqlalchemy.ext.hybrid import hybrid_property

from app.database.database import Base

TIPO_ADMIN = "admin"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    senha = Column(String(255), nullable=False)

    # O papel do utilizador vive SÓ em `tipo` (cliente, corretor ou admin).
    tipo = Column(String(20), nullable=False, default="cliente")

    # Resumo diário dos alertas por e-mail (pode ser desligado pela ligação do e-mail).
    alertas_por_email = Column(Boolean, nullable=False, default=True, server_default=true())
    ultimo_resumo_email_em = Column(DateTime, nullable=True)

    @hybrid_property
    def admin(self) -> bool:
        """Derivado de `tipo`; também funciona em consultas (Usuario.admin)."""
        return self.tipo == TIPO_ADMIN

    @admin.setter
    def admin(self, valor: bool) -> None:
        if valor:
            self.tipo = TIPO_ADMIN
        elif self.tipo == TIPO_ADMIN:
            self.tipo = "cliente"

    @admin.expression
    def admin(cls):
        return cls.tipo == TIPO_ADMIN
