from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field
from schemas.common import Timestamps
from schemas.enums import SiembraEstadoEnum


class SiembraEstanqueBase(BaseModel):
    siembra_plan_id: int
    estanque_id: int
    estado: SiembraEstadoEnum = SiembraEstadoEnum.p
    fecha_tentativa: Optional[date] = None
    fecha_siembra: Optional[date] = None
    lote: Optional[str] = Field(None, max_length=80)
    densidad_override_org_m2: Optional[float] = Field(None, ge=0)
    talla_inicial_override_g: Optional[float] = Field(None, ge=0)


class SiembraEstanqueCreate(SiembraEstanqueBase):
    created_by: Optional[int] = None


class SiembraEstanqueUpdate(BaseModel):
    estado: Optional[SiembraEstadoEnum] = None
    fecha_tentativa: Optional[date] = None
    fecha_siembra: Optional[date] = None
    densidad_override_org_m2: Optional[float] = None
    talla_inicial_override_g: Optional[float] = None
    lote: Optional[str] = None


class SiembraEstanqueOut(SiembraEstanqueBase, Timestamps):
    siembra_estanque_id: int
    created_by: Optional[int]

    class Config:
        orm_mode = True
