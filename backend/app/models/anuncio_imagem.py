from sqlalchemy import Column, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import deferred, relationship

from app.database.database import Base


class AnuncioImagem(Base):
    """Foto de um anúncio: um endereço externo (url) ou um ficheiro carregado.

    Os ficheiros carregados ficam na própria base (`conteudo`, reduzidos no aparelho
    antes do envio) e são servidos em /anuncios-imoveis/fotos/{chave}; `url` guarda
    esse caminho. A chave é aleatória: só vê a foto quem tem o endereço.
    """

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

    # Ficheiro carregado (vazio nas fotos por endereço externo). `deferred`: as listas
    # de anúncios não carregam os bytes das fotos.
    chave = Column(String(32), nullable=True, unique=True, index=True)
    tipo_mime = Column(String(30), nullable=True)
    tamanho = Column(Integer, nullable=True)
    conteudo = deferred(Column(LargeBinary, nullable=True))

    anuncio = relationship(
        "AnuncioImovel",
        back_populates="fotos",
    )
