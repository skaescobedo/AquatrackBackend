from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field, condecimal, model_validator

# =====================================================
# 🟢 INPUT SCHEMAS
# =====================================================

class BiometriaCreate(BaseModel):
    """Schema para registrar una nueva biometría"""
    n_muestra: int = Field(..., gt=0, description="Número de organismos en la muestra (>0)")
    peso_muestra_g: condecimal(ge=0, max_digits=10, decimal_places=3) = Field(..., description="Peso total en gramos")
    sob_usada_pct: Optional[condecimal(ge=0, le=100, max_digits=5, decimal_places=2)] = Field(
        None,
        description="SOB en 0-100. Si no se provee y actualiza_sob_operativa=False, usa SOB operativo actual"
    )
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
        if self.actualiza_sob_operativa:
            if not self.sob_fuente:
                raise ValueError(
                    "sob_fuente es requerido cuando actualiza_sob_operativa=True. "
                    "Valores: 'operativa_actual', 'ajuste_manual', 'reforecast'"
                )
            if self.sob_usada_pct is None:
                raise ValueError(
                    "sob_usada_pct es requerido cuando actualiza_sob_operativa=True"
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


class BiometriaCreateResponse(BaseModel):
    """Respuesta extendida con resultado de reforecast"""
    biometria: BiometriaOut
    reforecast_result: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# =====================================================
# 🔵 CONTEXTO SCHEMAS (para pre-carga en formulario)
# =====================================================

class SiembraContextOut(BaseModel):
    """Datos de siembra para contexto"""
    fecha_siembra: datetime
    dias_ciclo: int
    densidad_base_org_m2: float
    talla_inicial_g: float

    class Config:
        from_attributes = True


class SOBOperativoOut(BaseModel):
    """SOB operativo actual del estanque"""
    valor_pct: float = Field(..., description="SOB operativo actual (0-100)")
    fuente: str = Field(..., description="Origen del SOB: operativa_actual, ajuste_manual, reforecast")

    class Config:
        from_attributes = True


class PoblacionEstimadaOut(BaseModel):
    """Población estimada actual del estanque"""
    densidad_efectiva_org_m2: float = Field(..., description="Densidad después de retiros y mortalidad")
    organismos_totales: int = Field(..., description="Total de organismos estimados en el estanque")

    class Config:
        from_attributes = True


class UltimaBiometriaContextOut(BaseModel):
    """Datos de última biometría para contexto"""
    fecha: datetime
    pp_g: float
    sob_usada_pct: float
    dias_desde: int

    class Config:
        from_attributes = True


class ProyeccionVigenteContextOut(BaseModel):
    """Valores de proyección vigente para referencia"""
    semana_actual: int
    sob_proyectado_pct: float
    pp_proyectado_g: float
    fuente: Literal["draft", "published"]

    class Config:
        from_attributes = True


class BiometriaContextOut(BaseModel):
    """
    Contexto completo para registrar una biometría.
    
    Provee todos los datos necesarios para:
    - Pre-cargar el SOB operativo actual en el formulario
    - Calcular preview de biomasa y densidad
    - Mostrar valores de referencia de la proyección
    """
    estanque_id: int
    estanque_nombre: str
    area_m2: float
    
    siembra: SiembraContextOut
    sob_operativo_actual: SOBOperativoOut
    retiros_acumulados_org_m2: float
    poblacion_estimada: PoblacionEstimadaOut
    
    ultima_biometria: Optional[UltimaBiometriaContextOut] = None
    proyeccion_vigente: Optional[ProyeccionVigenteContextOut] = None

    class Config:
        from_attributes = True
