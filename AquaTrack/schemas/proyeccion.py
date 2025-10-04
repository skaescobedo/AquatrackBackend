from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional


class ProyeccionBase(BaseModel):
    ciclo_id: int
    version: str = Field(..., max_length=20)
    descripcion: Optional[str]
    status: str = Field(default='b', pattern='^[bprx]$')  # b=borrador, p=publicada, r=revisada, x=cancelada
    is_current: bool = False
    sob_final_objetivo_pct: Optional[float] = Field(None, ge=0, le=100)
    source_type: Optional[str] = Field(None, pattern='^(auto|archivo|reforecast)?$')
    source_ref: Optional[str] = Field(None, max_length=120)
    parent_version_id: Optional[int]
    siembra_ventana_inicio: Optional[date]


class ProyeccionCreate(ProyeccionBase):
    creada_por: Optional[int]


class ProyeccionUpdate(BaseModel):
    descripcion: Optional[str]
    status: Optional[str] = Field(None, pattern='^[bprx]$')
    sob_final_objetivo_pct: Optional[float] = Field(None, ge=0, le=100)
    is_current: Optional[bool]


class ProyeccionOut(ProyeccionBase):
    proyeccion_id: int
    publicada_at: Optional[datetime]
    creada_por: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
