from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database.database import Base


class AnuncioImagem(Base):
    __tablename__ = "anuncio_imagens"

    id = Column(Integer, primary_key=True, index=True)

    anuncio_id = Column(
        Integer,
        ForeignKey("anuncios_imoveis.id"),
        nullable=False,
        index=True,
    )

    url = Column(String(500), nullable=False)

    ordem = Column(Integer, nullable=False, default=0)

    anuncio = relationship(
        "AnuncioImovel",
        back_populates="fotos",
    )

fotos = relationship(
    "AnuncioImagem",
    back_populates="anuncio",
    cascade="all, delete-orphan",
    order_by="AnuncioImagem.ordem",
)

@property
def imagens(self):
    return [foto.url for foto in self.fotos]