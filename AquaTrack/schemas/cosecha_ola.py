from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field
from enums.enums import CosechaTipoEnum, CosechaEstadoEnum
from schemas.common import Timestamps


class CosechaOlaBase(BaseModel):
    plan_cosechas_id: int
    nombre: str = Field(..., max_length=120)
    tipo: CosechaTipoEnum
    ventana_inicio: date
    ventana_fin: date
    objetivo_retiro_org_m2: Optional[float] = Field(None, ge=0)
    estado: CosechaEstadoEnum = CosechaEstadoEnum.p
    orden: Optional[int] = None
    notas: Optional[str] = Field(None, max_length=255)


class CosechaOlaCreate(CosechaOlaBase):
    created_by: Optional[int] = None


class CosechaOlaUpdate(BaseModel):
    ventana_inicio: Optional[date] = None
    ventana_fin: Optional[date] = None
    estado: Optional[CosechaEstadoEnum] = None
    notas: Optional[str] = None


class CosechaOlaOut(CosechaOlaBase, Timestamps):
    cosecha_ola_id: int
    created_by: Optional[int]

    model_config = {"from_attributes": True}
