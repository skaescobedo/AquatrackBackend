from datetime import date
from typing import Optional
from pydantic import BaseModel, Field
from enums.enums import CicloEstadoEnum
from schemas.common import Timestamps


class CicloBase(BaseModel):
    granja_id: int
    nombre: str = Field(..., max_length=150)
    fecha_inicio: date
    fecha_fin_planificada: Optional[date] = None
    observaciones: Optional[str] = None
    estado: CicloEstadoEnum = CicloEstadoEnum.a


class CicloCreate(CicloBase):
    pass


class CicloUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=150)
    fecha_inicio: Optional[date] = None
    fecha_fin_planificada: Optional[date] = None
    fecha_cierre_real: Optional[date] = None
    estado: Optional[CicloEstadoEnum] = None
    observaciones: Optional[str] = None


class CicloOut(CicloBase, Timestamps):
    ciclo_id: int
    fecha_cierre_real: Optional[date]

    model_config = {"from_attributes": True}