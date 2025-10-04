from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional


class TareaBase(BaseModel):
    granja_id: Optional[int]
    titulo: str = Field(..., max_length=160)
    descripcion: Optional[str]
    prioridad: str = Field(default='m', pattern='^[bma]$')  # baja, media, alta
    fecha_limite: Optional[date]
    tiempo_estimado_horas: Optional[float] = Field(None, ge=0)
    estado: str = Field(default='p', pattern='^[pecx]$')  # pendiente, en curso, completada, cancelada
    tipo: Optional[str] = Field(None, max_length=80)
    periodo_clave: Optional[str] = Field(None, max_length=40)
    es_recurrente: bool = False


class TareaCreate(TareaBase):
    created_by: Optional[int]


class TareaUpdate(BaseModel):
    titulo: Optional[str]
    descripcion: Optional[str]
    prioridad: Optional[str] = Field(None, pattern='^[bma]$')
    estado: Optional[str] = Field(None, pattern='^[pecx]$')
    fecha_limite: Optional[date]
    tiempo_estimado_horas: Optional[float] = Field(None, ge=0)
    es_recurrente: Optional[bool]
    tipo: Optional[str]
    periodo_clave: Optional[str]


class TareaOut(TareaBase):
    tarea_id: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
