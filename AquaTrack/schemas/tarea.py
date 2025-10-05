from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field
from schemas.common import Timestamps
from enums.enums import TareaPrioridadEnum, TareaEstadoEnum


class TareaBase(BaseModel):
    granja_id: Optional[int] = None
    titulo: str = Field(..., max_length=160)
    descripcion: Optional[str] = None
    prioridad: TareaPrioridadEnum = TareaPrioridadEnum.m
    fecha_limite: Optional[date] = None
    tiempo_estimado_horas: Optional[float] = Field(None, ge=0)
    estado: TareaEstadoEnum = TareaEstadoEnum.p
    tipo: Optional[str] = Field(None, max_length=80)
    periodo_clave: Optional[str] = Field(None, max_length=40)
    es_recurrente: bool = False


class TareaCreate(TareaBase):
    # created_by lo tomarás del usuario autenticado (dependency),
    # por eso no lo exigimos aquí. Si decides enviarlo desde el cliente,
    # puedes agregar: created_by: Optional[int] = None
    pass


class TareaUpdate(BaseModel):
    granja_id: Optional[int] = None
    titulo: Optional[str] = Field(None, max_length=160)
    descripcion: Optional[str] = None
    prioridad: Optional[TareaPrioridadEnum] = None
    fecha_limite: Optional[date] = None
    tiempo_estimado_horas: Optional[float] = Field(None, ge=0)
    estado: Optional[TareaEstadoEnum] = None
    tipo: Optional[str] = Field(None, max_length=80)
    periodo_clave: Optional[str] = Field(None, max_length=40)
    es_recurrente: Optional[bool] = None


class TareaOut(TareaBase, Timestamps):
    tarea_id: int
    created_by: Optional[int] = None

    model_config = {"from_attributes": True}