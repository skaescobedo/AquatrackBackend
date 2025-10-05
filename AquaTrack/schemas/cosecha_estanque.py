from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field
from enums.enums import CosechaEstadoDetEnum
from schemas.common import Timestamps


class CosechaEstanqueBase(BaseModel):
    estanque_id: int
    cosecha_ola_id: int
    estado: CosechaEstadoDetEnum = CosechaEstadoDetEnum.p
    fecha_cosecha: date
    pp_g: Optional[float] = Field(None, ge=0)
    biomasa_kg: Optional[float] = Field(None, ge=0)
    densidad_retirada_org_m2: Optional[float] = Field(None, ge=0)
    notas: Optional[str] = Field(None, max_length=255)


class CosechaEstanqueCreate(CosechaEstanqueBase):
    created_by: Optional[int] = None
    confirmado_por: Optional[int] = None


class CosechaEstanqueUpdate(BaseModel):
    estado: Optional[CosechaEstadoDetEnum] = None
    fecha_cosecha: Optional[date] = None
    pp_g: Optional[float] = Field(None, ge=0)                 # <- agregado
    biomasa_kg: Optional[float] = Field(None, ge=0)
    densidad_retirada_org_m2: Optional[float] = Field(None, ge=0)
    notas: Optional[str] = Field(None, max_length=255)


class CosechaEstanqueOut(CosechaEstanqueBase, Timestamps):
    cosecha_estanque_id: int
    created_by: Optional[int]
    confirmado_por: Optional[int]
    confirmado_event_at: Optional[datetime]

    model_config = {"from_attributes": True}
