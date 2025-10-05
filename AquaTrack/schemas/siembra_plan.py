from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field
from schemas.common import Timestamps


class SiembraPlanBase(BaseModel):
    ciclo_id: int
    ventana_inicio: date
    ventana_fin: date
    densidad_org_m2: float = Field(..., ge=0)
    talla_inicial_g: float = Field(..., ge=0)
    observaciones: Optional[str] = None


class SiembraPlanCreate(SiembraPlanBase):
    created_by: Optional[int] = None


class SiembraPlanUpdate(BaseModel):
    ventana_inicio: Optional[date] = None
    ventana_fin: Optional[date] = None
    densidad_org_m2: Optional[float] = Field(None, ge=0)
    talla_inicial_g: Optional[float] = Field(None, ge=0)
    observaciones: Optional[str] = None


class SiembraPlanOut(SiembraPlanBase, Timestamps):
    siembra_plan_id: int
    created_by: Optional[int]

    model_config = {"from_attributes": True}
