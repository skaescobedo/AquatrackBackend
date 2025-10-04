from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class UsuarioGranjaBase(BaseModel):
    usuario_id: int
    granja_id: int
    estado: str = Field(default='a', pattern='^[ai]$')


class UsuarioGranjaCreate(UsuarioGranjaBase):
    pass


class UsuarioGranjaUpdate(BaseModel):
    estado: Optional[str] = Field(None, pattern='^[ai]$')


class UsuarioGranjaOut(UsuarioGranjaBase):
    usuario_granja_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
