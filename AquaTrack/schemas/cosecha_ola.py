from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional


class CosechaOlaBase(BaseModel):
    plan_cosechas_id: int
    nombre: str
    tipo: str = Field(..., pattern="^[pf]$")
    ventana_inicio: date
    ventana_fin: date
    objetivo_retiro_org_m2: Optional[float] = Field(None, ge=0)
    estado: str = Field(default="p", pattern="^[prx]$")
    orden: Optional[int]
    notas: Optional[str]


class CosechaOlaCreate(CosechaOlaBase):
    created_by: Optional[int]


class CosechaOlaOut(CosechaOlaBase):
    cosecha_ola_id: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
