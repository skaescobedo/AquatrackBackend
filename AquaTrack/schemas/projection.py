# schemas/projection.py
from __future__ import annotations

from datetime import datetime, date
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, condecimal, field_validator, model_validator


# ===================================
# CANONICAL PROJECTION (Gemini)
# ===================================

class CanonicalLineaProjection(BaseModel):
    """
    Línea semanal extraída por Gemini (esquema canónico).
    Todos los campos ya vienen normalizados y derivados.
    """
    semana_idx: int = Field(ge=0, description="Índice de semana (0, 1, 2, ...)")
    fecha_plan: date
    edad_dias: int = Field(ge=0, description="Edad en días (0, 7, 14, ...)")
    pp_g: float = Field(ge=0, description="Peso promedio en gramos")
    incremento_g_sem: float = Field(ge=0, description="Incremento semanal en gramos")
    sob_pct_linea: float = Field(ge=0, le=100, description="Supervivencia (%) 0-100")
    cosecha_flag: bool = False
    retiro_org_m2: float | None = Field(None, ge=0)
    nota: str | None = None


class CanonicalProjection(BaseModel):
    """
    Proyección canónica extraída por Gemini.

    Incluye:
    - Parámetros top-level opcionales (siembra, densidad, SOB objetivo)
    - Lista de líneas semanales ya normalizadas
    """
    # Parámetros top-level (opcionales)
    siembra_ventana_inicio: date | None = None
    siembra_ventana_fin: date | None = None
    densidad_org_m2: float | None = Field(None, ge=0)
    talla_inicial_g: float | None = Field(None, ge=0)
    sob_final_objetivo_pct: float | None = Field(None, ge=0, le=100)

    # Líneas semanales (requeridas, al menos 1)
    lineas: List[CanonicalLineaProjection] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_lines_order(self):
        """Valida que las líneas estén ordenadas por fecha"""
        if len(self.lineas) > 1:
            for i in range(len(self.lineas) - 1):
                if self.lineas[i].fecha_plan > self.lineas[i + 1].fecha_plan:
                    raise ValueError("Las líneas deben estar ordenadas por fecha_plan ascendente")
        return self


# ===================================
# LÍNEA DE PROYECCIÓN (semana)
# ===================================

class ProyeccionLineaBase(BaseModel):
    edad_dias: int = Field(ge=0, description="Edad en días del cultivo")
    semana_idx: int = Field(ge=0, description="Índice de semana (0, 1, 2, ...)")
    fecha_plan: date
    pp_g: condecimal(ge=0, max_digits=7, decimal_places=3)
    incremento_g_sem: condecimal(ge=0, max_digits=7, decimal_places=3) | None = None
    sob_pct_linea: condecimal(ge=0, le=100, max_digits=5, decimal_places=2)
    cosecha_flag: bool = False
    retiro_org_m2: condecimal(ge=0, max_digits=12, decimal_places=4) | None = None
    nota: str | None = Field(None, max_length=255)


class ProyeccionLineaCreate(ProyeccionLineaBase):
    """Schema para crear una línea de proyección"""
    pass


class ProyeccionLineaOut(ProyeccionLineaBase):
    """Schema de salida con ID"""
    proyeccion_linea_id: int
    proyeccion_id: int

    class Config:
        from_attributes = True


# ===================================
# PROYECCIÓN (versión completa)
# ===================================

class ProyeccionBase(BaseModel):
    version: str = Field(max_length=20, description="Identificador de versión (V1, V2, V3, ...)")
    descripcion: str | None = Field(None, max_length=255)
    sob_final_objetivo_pct: condecimal(ge=0, le=100, max_digits=5, decimal_places=2) | None = None
    siembra_ventana_fin: date | None = None


class ProyeccionCreate(ProyeccionBase):
    """Schema para crear proyección manualmente (sin archivo)"""
    lineas: List[ProyeccionLineaCreate] = Field(min_length=1, description="Líneas semanales de proyección")

    @field_validator('version')
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        if not v.upper().startswith('V'):
            raise ValueError("La versión debe comenzar con 'V' (ej: V1, V2, V3)")
        return v.upper()


class ProyeccionFromFileCreate(ProyeccionBase):
    """
    Schema para crear proyección desde archivo.
    No incluye 'lineas' porque se generan automáticamente desde el archivo.
    """
    source_ref: str | None = Field(None, max_length=120, description="Nombre del archivo original")


class ProyeccionUpdate(BaseModel):
    """Schema para actualizar proyección (solo metadatos)"""
    descripcion: str | None = Field(None, max_length=255)
    sob_final_objetivo_pct: condecimal(ge=0, le=100, max_digits=5, decimal_places=2) | None = None
    siembra_ventana_fin: date | None = None


class ProyeccionOut(ProyeccionBase):
    """Schema de salida básico (sin líneas)"""
    proyeccion_id: int
    ciclo_id: int
    status: Literal['b', 'p', 'r', 'x']
    is_current: bool
    published_at: datetime | None
    creada_por: int | None
    source_type: Literal['planes', 'archivo', 'reforecast'] | None
    source_ref: str | None = None
    parent_version_id: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProyeccionDetailOut(ProyeccionOut):
    """Schema de salida completo (con líneas)"""
    lineas: List[ProyeccionLineaOut] = []

    class Config:
        from_attributes = True


# ===================================
# PUBLICACIÓN Y GESTIÓN
# ===================================

class ProyeccionPublish(BaseModel):
    """Payload para publicar una proyección"""
    confirmar_publicacion: bool = Field(
        default=False,
        description="Confirmar que se desea publicar (se congelará la versión)"
    )

    @field_validator('confirmar_publicacion')
    @classmethod
    def must_be_true(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Debe confirmar explícitamente la publicación")
        return v


# ===================================
# RESPUESTA DE INGESTA (metadata)
# ===================================

class IngestMetadata(BaseModel):
    """Metadata de la ingesta (NO es el JSON de Gemini, solo info adicional)"""
    archivo_nombre: str
    archivo_mime: str
    procesado_en: datetime = Field(default_factory=datetime.now)