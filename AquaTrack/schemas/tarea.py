from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from decimal import Decimal

class TareaOut(BaseModel):
    tarea_id: int
    titulo: str
    descripcion: Optional[str]
    prioridad: str
    fecha_limite: Optional[date]
    tiempo_estimado_horas: Optional[Decimal]
    estado: str
    tipo: Optional[str]
    periodo_clave: Optional[str]
    es_recurrente: str
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TareaCreate(BaseModel):
    titulo: str
    descripcion: Optional[str] = None
    prioridad: str = "m"
    fecha_limite: Optional[date] = None
    tiempo_estimado_horas: Optional[Decimal] = None
    estado: str = "p"
    tipo: Optional[str] = None
    periodo_clave: Optional[str] = None
    es_recurrente: str = "0"
    created_by: Optional[int] = None

class TareaUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    prioridad: Optional[str] = None
    fecha_limite: Optional[date] = None
    tiempo_estimado_horas: Optional[Decimal] = None
    estado: Optional[str] = None
    tipo: Optional[str] = None
    periodo_clave: Optional[str] = None
    es_recurrente: Optional[str] = None
