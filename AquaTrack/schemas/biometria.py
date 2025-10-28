from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, condecimal, model_validator

# =====================================================
# 🟢 INPUT SCHEMAS (para crear biometrías)
# =====================================================

class BiometriaCreate(BaseModel):
    """
    Schema para registrar una nueva biometría.

    Reglas de negocio:
    - La fecha NO viene en el payload; la fija el servidor en America/Mazatlan.
    - Si actualiza_sob_operativa=True, sob_fuente es REQUERIDO.
    - pp_g e incremento_g_sem se calculan automáticamente.
    """
    n_muestra: int = Field(..., gt=0, description="Número de organismos en la muestra (>0)")
    peso_muestra_g: condecimal(ge=0, max_digits=10, decimal_places=3) = Field(..., description="Peso total en gramos")
    sob_usada_pct: condecimal(ge=0, le=100, max_digits=5, decimal_places=2) = Field(..., description="SOB en 0-100")

    notas: Optional[str] = Field(None, max_length=255, description="Observaciones")

    actualiza_sob_operativa: bool = Field(
        default=False,
        description="Si True, esta biometría actualizará el SOB operativo del estanque"
    )
    sob_fuente: Optional[Literal["operativa_actual", "ajuste_manual", "reforecast"]] = Field(
        None,
        description="Origen del valor de SOB (requerido si actualiza_sob_operativa=True)"
    )
    motivo_cambio_sob: Optional[str] = Field(None, max_length=255, description="Motivo del cambio de SOB")

    @model_validator(mode='after')
    def validate_sob_update_logic(self):
        if self.actualiza_sob_operativa and not self.sob_fuente:
            raise ValueError(
                "sob_fuente es requerido cuando actualiza_sob_operativa=True. "
                "Valores: 'operativa_actual', 'ajuste_manual', 'reforecast'"
            )
        if not self.actualiza_sob_operativa:
            self.sob_fuente = None
            self.motivo_cambio_sob = None
        return self


class BiometriaUpdate(BaseModel):
    """Actualización permitida solo de 'notas' cuando la biometría no cambió SOB."""
    notas: Optional[str] = Field(None, max_length=255)

# =====================================================
# 🟣 OUTPUT SCHEMAS
# =====================================================

class BiometriaOut(BaseModel):
    biometria_id: int
    ciclo_id: int
    estanque_id: int

    fecha: datetime
    n_muestra: int
    peso_muestra_g: float
    pp_g: float
    sob_usada_pct: float
    incremento_g_sem: Optional[float] = None

    notas: Optional[str] = None
    actualiza_sob_operativa: bool
    sob_fuente: Optional[str] = None

    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BiometriaListOut(BaseModel):
    biometria_id: int
    fecha: datetime
    pp_g: float
    sob_usada_pct: float
    incremento_g_sem: Optional[float] = None
    actualiza_sob_operativa: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SOBCambioLogOut(BaseModel):
    sob_cambio_log_id: int
    estanque_id: int
    ciclo_id: int
    sob_anterior_pct: float
    sob_nueva_pct: float
    fuente: str
    motivo: Optional[str] = None
    changed_by: int
    changed_at: datetime

    class Config:
        from_attributes = True


class BiometriaStats(BaseModel):
    estanque_id: int
    total_muestras: int
    pp_promedio_g: float
    pp_max_g: float
    pp_min_g: float
    sob_promedio_pct: float
    ultima_biometria_fecha: Optional[datetime] = None
    incremento_promedio_g_sem: Optional[float] = None


class CicloGrowthSummary(BaseModel):
    ciclo_id: int
    total_biometrias: int
    pp_promedio_general_g: float
    sob_promedio_general_pct: float
    estanques_con_biometria: int
    fecha_primera_biometria: Optional[datetime] = None
    fecha_ultima_biometria: Optional[datetime] = None
