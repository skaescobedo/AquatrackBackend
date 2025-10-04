from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional


class CicloBase(BaseModel):
    granja_id: int
    nombre: str = Field(..., max_length=150)
    fecha_inicio: date
    fecha_fin_planificada: Optional[date]
    observaciones: Optional[str]
    estado: str = Field(default='a', pattern='^[at]$')  # a=activo, t=terminado


class CicloCreate(CicloBase):
    pass


class CicloUpdate(BaseModel):
    nombre: Optional[str]
    fecha_inicio: Optional[date]
    fecha_fin_planificada: Optional[date]
    fecha_cierre_real: Optional[date]
    observaciones: Optional[str]
    estado: Optional[str] = Field(None, pattern='^[at]$')


class CicloOut(CicloBase):
    ciclo_id: int
    fecha_cierre_real: Optional[date]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
