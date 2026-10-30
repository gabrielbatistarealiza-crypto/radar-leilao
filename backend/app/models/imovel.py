from sqlalchemy import Column, Integer, String, Float, Date, Boolean, ForeignKey, DateTime, and_, case, func, true
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property
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
    valor_leilao = Column(Float)  # "Preço" da lista da Caixa (nos leilões SFI = avaliação)
    desconto = Column(Float)  # "Desconto" da lista da Caixa
    # Valores de venda do edital (Anexo II). A lista da Caixa não os traz.
    valor_primeiro_leilao = Column(Float, nullable=True)
    valor_segundo_leilao = Column(Float, nullable=True)

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

    # Lista da Caixa: um imóvel que deixa de aparecer numa lista completa não é
    # apagado; fica na_lista=False (fora da pesquisa) e volta se reaparecer.
    na_lista = Column(Boolean, nullable=False, default=True, server_default=true())
    saiu_da_lista_em = Column(DateTime, nullable=True)
    visto_na_lista_em = Column(DateTime, nullable=True)

    eventos = relationship(
        "ImovelEvento",
        back_populates="imovel",
        cascade="all, delete-orphan",
        order_by="ImovelEvento.momento",
        passive_deletes=True,
    )

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

    @hybrid_property
    def valor_lance(self):
        """Preço mínimo para arrematar: o menor lance do edital, ou o preço da lista.

        Normalmente é o 2.º leilão; quando a dívida faz o 2.º ficar acima do 1.º,
        é o 1.º."""
        lances = [v for v in (self.valor_primeiro_leilao, self.valor_segundo_leilao) if v is not None]
        return min(lances) if lances else self.valor_leilao

    @valor_lance.expression
    def valor_lance(cls):
        v1, v2 = cls.valor_primeiro_leilao, cls.valor_segundo_leilao
        return case(
            (and_(v1.isnot(None), v2.isnot(None), v1 < v2), v1),
            else_=func.coalesce(v2, v1, cls.valor_leilao),
        )

    @property
    def desconto_atual(self):
        """Desconto do lance mínimo sobre a avaliação; sem edital, o da lista."""
        if self.valor_primeiro_leilao is None and self.valor_segundo_leilao is None:
            return self.desconto
        if not self.valor_avaliacao or self.valor_avaliacao <= 0:
            return None
        return round((self.valor_avaliacao - self.valor_lance) / self.valor_avaliacao * 100, 2)

    @property
    def economia_m2(self):
        if (
            self.valor_avaliacao is None
            or self.valor_lance is None
            or self.area is None
            or self.area <= 0
        ):
            return None

        return (self.valor_avaliacao - self.valor_lance) / self.area


class ImovelImagem(Base):

    __tablename__ = "imovel_imagens"

    id = Column(Integer, primary_key=True, index=True)
    imovel_id = Column(Integer, ForeignKey("imoveis.id"), nullable=False, index=True)
    url = Column(String(500), nullable=False)
    ordem = Column(Integer, nullable=False, default=0)

    imovel = relationship("Imovel", back_populates="fotos")

class ImovelEvento(Base):
    """Histórico do imóvel na lista da Caixa: entrou, saiu, voltou, mudou de preço."""

    __tablename__ = "imovel_eventos"

    ENTROU = "ENTROU_NA_LISTA"
    SAIU = "SAIU_DA_LISTA"
    VOLTOU = "VOLTOU_A_LISTA"
    PRECO = "PRECO_ALTERADO"
    DATAS = "DATAS_DO_NOVO_EDITAL"  # datas vencidas substituídas por um edital novo

    id = Column(Integer, primary_key=True, index=True)
    imovel_id = Column(
        Integer, ForeignKey("imoveis.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo = Column(String(30), nullable=False)
    momento = Column(DateTime, nullable=False, default=datetime.utcnow)
    valor_anterior = Column(Float, nullable=True)
    valor_novo = Column(Float, nullable=True)

    imovel = relationship("Imovel", back_populates="eventos")


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
