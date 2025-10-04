from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional


class SiembraPlanBase(BaseModel):
    ciclo_id: int
    ventana_inicio: date
    ventana_fin: date
    densidad_org_m2: float = Field(..., ge=0)
    talla_inicial_g: float = Field(..., ge=0)
    observaciones: Optional[str]


class SiembraPlanCreate(SiembraPlanBase):
    created_by: Optional[int]


class SiembraPlanUpdate(BaseModel):
    ventana_inicio: Optional[date]
    ventana_fin: Optional[date]
    densidad_org_m2: Optional[float]
    talla_inicial_g: Optional[float]
    observaciones: Optional[str]


class SiembraPlanOut(SiembraPlanBase):
    siembra_plan_id: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
