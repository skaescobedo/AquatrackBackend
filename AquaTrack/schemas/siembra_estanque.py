from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional


class SiembraEstanqueBase(BaseModel):
    siembra_plan_id: int
    estanque_id: int
    estado: str = Field(default="p", pattern="^[pf]$")
    fecha_tentativa: Optional[date]
    fecha_siembra: Optional[date]
    lote: Optional[str]
    densidad_override_org_m2: Optional[float] = Field(None, ge=0)
    talla_inicial_override_g: Optional[float] = Field(None, ge=0)


class SiembraEstanqueCreate(SiembraEstanqueBase):
    created_by: Optional[int]


class SiembraEstanqueUpdate(BaseModel):
    estado: Optional[str] = Field(None, pattern="^[pf]$")
    fecha_siembra: Optional[date]
    densidad_override_org_m2: Optional[float]
    talla_inicial_override_g: Optional[float]
    lote: Optional[str]


class SiembraEstanqueOut(SiembraEstanqueBase):
    siembra_estanque_id: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
