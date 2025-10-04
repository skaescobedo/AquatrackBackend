from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UsuarioBase(BaseModel):
    username: str = Field(..., max_length=20)
    nombre: str = Field(..., max_length=30)
    apellido1: str = Field(..., max_length=30)
    apellido2: Optional[str] = Field(None, max_length=30)
    email: EmailStr


class UsuarioCreate(UsuarioBase):
    password: str = Field(..., min_length=8)


class UsuarioUpdate(BaseModel):
    nombre: Optional[str]
    apellido1: Optional[str]
    apellido2: Optional[str]
    email: Optional[EmailStr]
    estado: Optional[str] = Field(None, pattern="^[ai]$")
    password: Optional[str]


class UsuarioOut(UsuarioBase):
    usuario_id: int
    estado: str
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

