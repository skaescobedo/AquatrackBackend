from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime

class CycleCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=150)
    fecha_inicio: date = Field(
        ...,
        description=(
            "Fecha de inicio del ciclo - Primera siembra planificada. "
            "Se sincronizará automáticamente con la fecha real al confirmar la última siembra."
        )
    )
    fecha_fin_planificada: date | None = None
    observaciones: str | None = None

    @field_validator('fecha_inicio')
    @classmethod
    def validate_fecha_inicio(cls, v):
        """Permite fechas futuras (planificación)"""
        # No hay restricción - puede ser pasado o futuro
        return v

class CycleUpdate(BaseModel):
    nombre: str | None = None
    fecha_fin_planificada: date | None = None
    observaciones: str | None = None

class CycleClose(BaseModel):
    fecha_cierre_real: date
    notas_cierre: str | None = None
    # Campos opcionales para cuando se implemente cálculo automático
    sob_final_real_pct: float | None = None
    toneladas_cosechadas: float | None = None
    n_estanques_cosechados: int | None = None

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