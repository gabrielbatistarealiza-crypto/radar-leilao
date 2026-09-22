from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field


class ImovelScraper(BaseModel):
    titulo: Optional[str] = None
    tipo: Optional[str] = None
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    valor_avaliacao: Optional[float] = None
    valor_leilao: Optional[float] = None
    desconto: Optional[float] = None
    data_primeiro_leilao: Optional[date] = None
    data_segundo_leilao: Optional[date] = None
    area_util: Optional[float] = None
    area: Optional[float] = None
    quartos: Optional[int] = None
    banheiros: Optional[int] = None
    vagas: Optional[int] = None
    url: Optional[str] = None
    imagem: Optional[str] = None
    imagens: List[str] = Field(default_factory=list)
    modalidade: Optional[str] = None
    fonte: Optional[str] = None

    class Config:
        from_attributes = True
