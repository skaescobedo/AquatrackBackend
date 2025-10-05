from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field
from enums.enums import ProyeccionStatusEnum, ProyeccionSourceEnum
from schemas.common import Timestamps


class ProyeccionBase(BaseModel):
    ciclo_id: int
    version: str = Field(..., max_length=20)
    descripcion: Optional[str] = Field(None, max_length=255)
    status: ProyeccionStatusEnum = ProyeccionStatusEnum.b
    is_current: bool = False
    source_type: Optional[ProyeccionSourceEnum] = None
    source_ref: Optional[str] = Field(None, max_length=120)
    sob_final_objetivo_pct: Optional[float] = Field(None, ge=0, le=100)
    siembra_ventana_inicio: Optional[date] = None


class ProyeccionCreate(ProyeccionBase):
    parent_version_id: Optional[int] = None


class ProyeccionUpdate(BaseModel):
    descripcion: Optional[str] = None
    status: Optional[ProyeccionStatusEnum] = None
    is_current: Optional[bool] = None
    sob_final_objetivo_pct: Optional[float] = Field(None, ge=0, le=100)


class ProyeccionOut(ProyeccionBase, Timestamps):
    proyeccion_id: int
    parent_version_id: Optional[int] = None
    published_at: Optional[datetime] = None
    creada_por: Optional[int] = None

    model_config = {"from_attributes": True}
