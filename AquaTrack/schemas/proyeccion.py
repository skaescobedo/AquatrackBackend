# schemas/proyeccion.py
from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field
from schemas.archivo import ArchivoOut
from schemas.archivo_proyeccion import ArchivoProyeccionOut
from schemas.common import Timestamps
from enums.enums import ProyeccionStatusEnum, ProyeccionSourceEnum

class ProyeccionBase(BaseModel):
    version: str = Field(..., max_length=20)
    descripcion: Optional[str] = Field(None, max_length=255)
    status: ProyeccionStatusEnum = ProyeccionStatusEnum.b
    source_type: Optional[ProyeccionSourceEnum] = None
    source_ref: Optional[str] = Field(None, max_length=120)
    parent_version_id: Optional[int] = None
    sob_final_objetivo_pct: Optional[float] = Field(None, ge=0, le=100)
    siembra_ventana_inicio: Optional[date] = None

class ProyeccionCreate(ProyeccionBase):
    pass

class ProyeccionUpdate(BaseModel):
    version: Optional[str] = Field(None, max_length=20)
    descripcion: Optional[str] = Field(None, max_length=255)
    # status no se edita por PATCH genérico; usar /publish
    source_type: Optional[ProyeccionSourceEnum] = None
    source_ref: Optional[str] = Field(None, max_length=120)
    parent_version_id: Optional[int] = None
    sob_final_objetivo_pct: Optional[float] = Field(None, ge=0, le=100)
    siembra_ventana_inicio: Optional[date] = None

class ProyeccionOut(ProyeccionBase, Timestamps):
    proyeccion_id: int
    ciclo_id: int
    is_current: bool
    published_at: Optional[datetime] = None
    creada_por: Optional[int] = None

    model_config = {"from_attributes": True}

class ProyeccionPublishIn(BaseModel):
    make_current: bool = True

class ProyeccionIngestaOut(BaseModel):
    proyeccion: ProyeccionOut
    archivo: ArchivoOut
    archivo_proyeccion: ArchivoProyeccionOut
    lineas_cargadas: int
