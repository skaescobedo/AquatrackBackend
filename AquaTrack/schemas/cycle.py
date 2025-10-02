# schemas/cycle.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Literal

from pydantic import Field, constr

from .shared import ORMModel
from .farm import GranjaMini


# ============================================================
# Ciclo (ciclo + resumen 1:1)
# ============================================================

# En DB: CheckConstraint("estado IN ('a','c')")
CicloEstadoChar = Literal['a', 'c']

class CicloBase(ORMModel):
    granja_id: int
    nombre: constr(strip_whitespace=True, min_length=1, max_length=150)
    fecha_inicio: date
    fecha_fin_planificada: Optional[date] = None
    fecha_cierre_real: Optional[date] = None
    estado: CicloEstadoChar = Field('a', description="a=activo, c=cerrado")
    observaciones: Optional[constr(strip_whitespace=True, max_length=255)] = None

class CicloCreate(CicloBase):
    pass

class CicloUpdate(ORMModel):
    granja_id: Optional[int] = None
    nombre: Optional[constr(strip_whitespace=True, min_length=1, max_length=150)] = None
    fecha_inicio: Optional[date] = None
    fecha_fin_planificada: Optional[date] = None
    fecha_cierre_real: Optional[date] = None
    estado: Optional[CicloEstadoChar] = None
    observaciones: Optional[constr(strip_whitespace=True, max_length=255)] = None

class CicloMini(ORMModel):
    ciclo_id: int
    nombre: str
    estado: CicloEstadoChar

class CicloRead(CicloBase):
    ciclo_id: int
    created_at: datetime
    updated_at: datetime
    # Enriquecimientos opcionales (si haces joinedload en servicios)
    granja: Optional[GranjaMini] = None


# ============================================================
# CicloResumen (1–1 con Ciclo)
# ============================================================

class CicloResumenRead(ORMModel):
    ciclo_id: int
    sob_final_real_pct: float     # Numeric(5,2) en DB; puedes validar rangos en servicios si gustas
    toneladas_cosechadas: float   # Numeric(14,3)
    n_estanques_cosechados: int

    fecha_inicio_real: Optional[date] = None
    fecha_fin_real: Optional[date] = None
    notas_cierre: Optional[constr(strip_whitespace=True, max_length=255)] = None

    created_at: datetime
    # Anidado opcional por conveniencia en lecturas
    ciclo: Optional[CicloMini] = None
