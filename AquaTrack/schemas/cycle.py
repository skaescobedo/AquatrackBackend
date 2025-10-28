from pydantic import BaseModel, Field
from datetime import date, datetime

class CycleCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=150)
    fecha_inicio: date
    fecha_fin_planificada: date | None = None
    observaciones: str | None = None

class CycleUpdate(BaseModel):
    nombre: str | None = None
    fecha_fin_planificada: date | None = None
    observaciones: str | None = None

class CycleClose(BaseModel):
    fecha_cierre_real: date
    notas_cierre: str | None = None

class CycleOut(BaseModel):
    ciclo_id: int
    granja_id: int
    nombre: str
    fecha_inicio: date
    fecha_fin_planificada: date | None
    fecha_cierre_real: date | None
    status: str
    observaciones: str | None
    created_at: datetime

    class Config:
        from_attributes = True

class CycleResumenOut(BaseModel):
    ciclo_id: int
    sob_final_real_pct: float
    toneladas_cosechadas: float
    n_estanques_cosechados: int
    fecha_inicio_real: date | None
    fecha_fin_real: date | None
    notas_cierre: str | None

    class Config:
        from_attributes = True