# schemas/biometrics.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Literal

from pydantic import Field, condecimal, constr, conint

from .shared import ORMModel
from .user import UsuarioMini
from .farm import EstanqueMini
from .cycle import CicloMini

# ============================================================
# Tipos / Literales
# ============================================================

# Enum de la app/BD para fuente de SOB en biometría y logs
SobFuenteLiteral = Literal["operativa_actual", "ajuste_manual", "reforecast"]


# ============================================================
# Biometría
# ============================================================

class BiometriaBase(ORMModel):
    ciclo_id: int
    estanque_id: int

    fecha: date
    n_muestra: conint(strict=True, gt=0)  # > 0 como en bio_chk_nmuestra

    # DECIMAL en BD -> condecimal en schema con validaciones
    peso_muestra_g: condecimal(ge=0, max_digits=13, decimal_places=3)  # DECIMAL(10,3) admite hasta 7 enteros + 3 dec; max_digits amplio por seguridad
    pp_g:            condecimal(ge=0, max_digits=10, decimal_places=3)  # DECIMAL(7,3)
    sob_usada_pct:   condecimal(ge=0, le=100, max_digits=5, decimal_places=2)

    incremento_g_sem: Optional[condecimal(ge=0, max_digits=10, decimal_places=3)] = None
    notas: Optional[constr(strip_whitespace=True, max_length=255)] = None

    actualiza_sob_operativa: bool = Field(False, description="Si True, propone actualizar SOB operativa del estanque.")
    sob_fuente: Optional[SobFuenteLiteral] = Field(
        default=None,
        description="Fuente de SOB si se usa/actualiza: operativa_actual | ajuste_manual | reforecast",
    )

    created_by: Optional[int] = Field(default=None, description="Usuario que registró la biometría (opcional).")

class BiometriaCreate(BiometriaBase):
    pass

class BiometriaUpdate(ORMModel):
    ciclo_id: Optional[int] = None
    estanque_id: Optional[int] = None

    fecha: Optional[date] = None
    n_muestra: Optional[conint(strict=True, gt=0)] = None

    peso_muestra_g: Optional[condecimal(ge=0, max_digits=13, decimal_places=3)] = None
    pp_g: Optional[condecimal(ge=0, max_digits=10, decimal_places=3)] = None
    sob_usada_pct: Optional[condecimal(ge=0, le=100, max_digits=5, decimal_places=2)] = None

    incremento_g_sem: Optional[condecimal(ge=0, max_digits=10, decimal_places=3)] = None
    notas: Optional[constr(strip_whitespace=True, max_length=255)] = None

    actualiza_sob_operativa: Optional[bool] = None
    sob_fuente: Optional[SobFuenteLiteral] = None

class BiometriaRead(BiometriaBase):
    biometria_id: int
    created_at: datetime
    updated_at: datetime

    # Enriquecimientos opcionales
    ciclo: Optional[CicloMini] = None
    estanque: Optional[EstanqueMini] = None
    creador: Optional[UsuarioMini] = None


# ============================================================
# SobCambioLog
# ============================================================

class SobCambioLogBase(ORMModel):
    estanque_id: int
    ciclo_id: int

    sob_anterior_pct: condecimal(ge=0, le=100, max_digits=5, decimal_places=2)
    sob_nueva_pct:    condecimal(ge=0, le=100, max_digits=5, decimal_places=2)

    fuente: SobFuenteLiteral
    motivo: Optional[constr(strip_whitespace=True, max_length=255)] = None

    changed_by: int

class SobCambioLogCreate(SobCambioLogBase):
    pass

class SobCambioLogRead(SobCambioLogBase):
    sob_cambio_log_id: int
    changed_at: datetime

    # Enriquecimientos opcionales
    ciclo: Optional[CicloMini] = None
    estanque: Optional[EstanqueMini] = None
    usuario: Optional[UsuarioMini] = None
