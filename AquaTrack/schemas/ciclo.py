from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date

class CicloOut(BaseModel):
    ciclo_id: int
    granja_id: int
    nombre: str
    fecha_inicio: date
    fecha_fin_planificada: Optional[date]
    fecha_cierre_real: Optional[date]
    estado: str
    observaciones: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CicloCreate(BaseModel):
    granja_id: int
    nombre: str
    fecha_inicio: date
    fecha_fin_planificada: Optional[date] = None
    observaciones: Optional[str] = None

class CicloUpdate(BaseModel):
    nombre: Optional[str] = None
    fecha_fin_planificada: Optional[date] = None
    fecha_cierre_real: Optional[date] = None
    estado: Optional[str] = None
    observaciones: Optional[str] = None
