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
    area: Optional[float] = None
    quartos: Optional[int] = None
    banheiros: Optional[int] = None
    vagas: Optional[int] = None
    url: Optional[str] = None
    imagem: Optional[str] = None
    modalidade: Optional[str] = None
    fonte: Optional[str] = None


class ImovelCreate(ImovelBase):
    imagens: List[str] = Field(default_factory=list)


class Imovel(ImovelBase):
    id: int
    criado_em: Optional[datetime] = None
    atualizado_em: Optional[datetime] = None
    imagens: List[str] = Field(default_factory=list)
    economia_m2: Optional[float] = None

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
