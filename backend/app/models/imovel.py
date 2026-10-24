from sqlalchemy import Column, Integer, String, Float, Date, Boolean, ForeignKey, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship

from app.database.database import Base


class Imovel(Base):

    __tablename__ = "imoveis"

    id = Column(Integer, primary_key=True, index=True)

    titulo = Column(String(255), nullable=False)
    tipo = Column(String(100))
    endereco = Column(String(255))
    cidade = Column(String(100))
    estado = Column(String(2))

    valor_avaliacao = Column(Float)
    valor_leilao = Column(Float)
    desconto = Column(Float)

    area = Column(Float, nullable=True)
    quartos = Column(Integer, nullable=True)
    banheiros = Column(Integer, nullable=True)
    vagas = Column(Integer, nullable=True)

    data_primeiro_leilao = Column(Date, nullable=True)
    data_segundo_leilao = Column(Date, nullable=True)
    data_licitacao_aberta = Column(Date, nullable=True)

    # None = não informado; True/False só quando a fonte informa de fato.
    ocupado = Column(Boolean, nullable=True)

    aceita_fgts = Column(Boolean, nullable=True)
    aceita_financiamento = Column(Boolean, nullable=True)

    link_edital = Column(String(500))

    fonte = Column(String(100), nullable=True)
    modalidade = Column(String(100), nullable=True)
    url = Column(String(500), nullable=True)
    url_imagem = Column(String(500), nullable=True)
    leiloeiro = Column(String(150), nullable=True)
    processo = Column(String(100), nullable=True)

    fotos = relationship(
        "ImovelImagem",
        back_populates="imovel",
        cascade="all, delete-orphan",
        order_by="ImovelImagem.ordem",
    )

    oportunidades = relationship(
        "Oportunidade",
        back_populates="imovel",
        cascade="all, delete-orphan",
    )

    @property
    def imagens(self):
        return [foto.url for foto in self.fotos]

    @property
    def economia_m2(self):
        if (
            self.valor_avaliacao is None
            or self.valor_leilao is None
            or self.area is None
            or self.area <= 0
        ):
            return None

        return (self.valor_avaliacao - self.valor_leilao) / self.area


class ImovelImagem(Base):

    __tablename__ = "imovel_imagens"

    id = Column(Integer, primary_key=True, index=True)
    imovel_id = Column(Integer, ForeignKey("imoveis.id"), nullable=False, index=True)
    url = Column(String(500), nullable=False)
    ordem = Column(Integer, nullable=False, default=0)

    imovel = relationship("Imovel", back_populates="fotos")

class ImovelFotoVerificacao(Base):
    __tablename__ = "imovel_foto_verificacoes"

    id = Column(Integer, primary_key=True, index=True)
    imovel_id = Column(
        Integer,
        ForeignKey("imoveis.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    resultado = Column(String(30), nullable=False)
    verificado_em = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
