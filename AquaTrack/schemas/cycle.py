from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from typing import Optional


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
    """
    Schema para cerrar un ciclo.

    Solo requiere fecha de cierre y observaciones opcionales.
    Las métricas (toneladas, sobrevivencia, etc.) se calculan on-demand
    desde las tablas operativas.
    """
    fecha_cierre_real: date
    observaciones: str | None = None


class CycleOut(BaseModel):
    """
    Schema de salida para ciclos.

    Campo adicional job_id: Si se subió archivo de proyección, contiene el job_id
    para hacer polling del estado de procesamiento. Si no hay archivo, job_id es null.
    """
    ciclo_id: int
    granja_id: int
    nombre: str
    fecha_inicio: date
    fecha_fin_planificada: date | None
    fecha_cierre_real: date | None
    status: str  # 'a' = activo, 'c' = cerrado
    observaciones: str | None
    created_at: datetime
    job_id: Optional[str] = None  # ← NUEVO: para polling de proyección asíncrona

    class Config:
        from_attributes = True

# NOTA: CycleResumenOut fue ELIMINADO
# Las métricas del ciclo se calculan on-demand desde:
# - siembras (densidades, fechas reales)
# - biometrías (crecimientos, sobrevivencias)
# - cosechas (toneladas, estanques cosechados)
#
# Esto es posible porque el versionamiento de estanques
# protege los datos históricos automáticamente.