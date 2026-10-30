from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ImovelImagemBase(BaseModel):
    url: str
    ordem: int = 0


class ImovelImagemCreate(ImovelImagemBase):
    pass


class ImovelImagem(ImovelImagemBase):
    id: int
    imovel_id: int
    criado_em: datetime

    class Config:
        from_attributes = True


class ImovelBase(BaseModel):
    titulo: str
    tipo: Optional[str] = None
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    valor_avaliacao: Optional[float] = None
    valor_leilao: Optional[float] = None
    desconto: Optional[float] = None
    data_primeiro_leilao: Optional[date] = None
    data_segundo_leilao: Optional[date] = None
    data_licitacao_aberta: Optional[date] = None
    area: Optional[float] = None
    quartos: Optional[int] = None
    banheiros: Optional[int] = None
    vagas: Optional[int] = None
    url: Optional[str] = None
    imagem: Optional[str] = None
    modalidade: Optional[str] = None
    fonte: Optional[str] = None
    link_edital: Optional[str] = None
    leiloeiro: Optional[str] = None
    processo: Optional[str] = None
    ocupado: Optional[bool] = None
    aceita_fgts: Optional[bool] = None
    aceita_financiamento: Optional[bool] = None


class ImovelCreate(ImovelBase):
    imagens: List[str] = Field(default_factory=list)


class Imovel(ImovelBase):
    id: int
    criado_em: Optional[datetime] = None
    atualizado_em: Optional[datetime] = None
    imagens: List[str] = Field(default_factory=list)
    economia_m2: Optional[float] = None
    # Valores do edital; valor_leilao passa a ser o menor destes (ou o da lista).
    valor_lista: Optional[float] = None
    valor_primeiro_leilao: Optional[float] = None
    valor_segundo_leilao: Optional[float] = None
    # False: saiu da lista da Caixa (continua na base, fora da pesquisa).
    na_lista: bool = True
    saiu_da_lista_em: Optional[datetime] = None

    class Config:
        from_attributes = True


class ImovelEvento(BaseModel):
    tipo: str
    momento: datetime
    valor_anterior: Optional[float] = None
    valor_novo: Optional[float] = None

    class Config:
        from_attributes = True



class ImoveisPaginados(BaseModel):
    items: List[Imovel]
    total: int
    pagina: int
    tamanho_pagina: int
    paginas_totais: int


# Aliases para compatibilidade com os routers
ImovelResponse = Imovel
ImovelPaginado = ImoveisPaginados
