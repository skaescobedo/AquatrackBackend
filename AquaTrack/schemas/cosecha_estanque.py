from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional


class CosechaEstanqueBase(BaseModel):
    estanque_id: int
    cosecha_ola_id: int
    tipo: str = Field(..., pattern="^[pf]$")
    estado: str = Field(default="p", pattern="^[pcx]$")
    fecha_cosecha: date
    pp_g: Optional[float] = Field(None, ge=0)
    biomasa_kg: Optional[float] = Field(None, ge=0)
    densidad_retirada_org_m2: Optional[float] = Field(None, ge=0)
    notas: Optional[str]


class CosechaEstanqueCreate(CosechaEstanqueBase):
    created_by: Optional[int]


class CosechaEstanqueUpdate(BaseModel):
    estado: Optional[str]
    fecha_cosecha: Optional[date]
    pp_g: Optional[float]
    biomasa_kg: Optional[float]
    densidad_retirada_org_m2: Optional[float]
    notas: Optional[str]
    confirmado_por: Optional[int]


class CosechaEstanqueOut(CosechaEstanqueBase):
    cosecha_estanque_id: int
    confirmado_por: Optional[int]
    confirmado_event_at: Optional[datetime]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
