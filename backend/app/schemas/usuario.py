from typing import Optional

from pydantic import BaseModel, EmailStr


TIPOS_USUARIO = {
    "cliente",
    "corretor",
    "admin",
}


class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    tipo: str = "cliente"


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    senha: Optional[str] = None
    admin: Optional[bool] = None
    tipo: Optional[str] = None


class UsuarioResponse(BaseModel):
    id: int
    nome: str
    email: EmailStr
    admin: bool
    tipo: str

    class Config:
        from_attributes = True