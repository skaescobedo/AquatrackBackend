from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

class CicloCreate(BaseModel):
    nombre: str = Field(..., max_length=150)
    fecha_inicio: date
    fecha_fin_planificada: Optional[date] = None
    observaciones: Optional[str] = None
    archivo_id: Optional[int] = None  # si viene, dispara ingesta -> borrador + líneas

class CicloOut(BaseModel):
    ciclo_id: int
    granja_id: int
    nombre: str
    fecha_inicio: date
    fecha_fin_planificada: Optional[date] = None
    estado: str
    observaciones: Optional[str] = None
    proyeccion_borrador_id: Optional[int] = None  # si se creó en este POST
