from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from schemas.enums import UsuarioEstadoEnum
from schemas.common import Timestamps


class UsuarioBase(BaseModel):
    username: str = Field(..., max_length=20)
    nombre: str = Field(..., max_length=30)
    apellido1: str = Field(..., max_length=30)
    apellido2: Optional[str] = Field(None, max_length=30)
    email: EmailStr


class UsuarioCreate(UsuarioBase):
    password: str = Field(..., min_length=8)


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=30)
    apellido1: Optional[str] = Field(None, max_length=30)
    apellido2: Optional[str] = Field(None, max_length=30)
    email: Optional[EmailStr]
    estado: Optional[UsuarioEstadoEnum] = None
    password: Optional[str] = Field(None, min_length=8)


class UsuarioOut(UsuarioBase, Timestamps):
    usuario_id: int
    estado: UsuarioEstadoEnum
    last_login_at: Optional[datetime]

    class Config:
        orm_mode = True
