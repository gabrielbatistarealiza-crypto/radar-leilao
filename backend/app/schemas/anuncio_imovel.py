from pydantic import BaseModel, Field

class AnuncioImagemResponse(BaseModel):
    id: int
    anuncio_id: int
    url: str
    ordem: int

    class Config:
        from_attributes = True


class AnuncioImovelResponse(BaseModel):
    id: int
    usuario_id: int
    corretor_id: int | None = None
    titulo: str
    tipo: str | None = None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None

    valor_mercado: float
    valor_anunciado: float
    desconto: float

    area: float | None = None
    quartos: int | None = None
    banheiros: int | None = None
    vagas: int | None = None

    descricao: str | None = None

    status: str
    ativo: bool
    motivo_rejeicao: str | None = None
    comissao_percentual: float | None = None
    comissao_aceite_em: object | None = None

    criado_em: object
    atualizado_em: object

    fotos: list[AnuncioImagemResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True