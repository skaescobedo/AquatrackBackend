# schemas/farm.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import Field, condecimal, constr

from .shared import ORMModel
from .user import UsuarioMini  # opcional para enriquecer lecturas de Estanque

# ============================================================
# Granja
# ============================================================

class GranjaBase(ORMModel):
    nombre: constr(strip_whitespace=True, min_length=1, max_length=150)
    ubicacion: Optional[constr(strip_whitespace=True, max_length=200)] = None
    descripcion: Optional[constr(strip_whitespace=True, max_length=255)] = None
    # Numeric(14,2) en DB; aquí validamos no-negativo.
    superficie_total_m2: condecimal(ge=0, max_digits=16, decimal_places=2)

class GranjaCreate(GranjaBase):
    pass

class GranjaUpdate(ORMModel):
    nombre: Optional[constr(strip_whitespace=True, min_length=1, max_length=150)] = None
    ubicacion: Optional[constr(strip_whitespace=True, max_length=200)] = None
    descripcion: Optional[constr(strip_whitespace=True, max_length=255)] = None
    superficie_total_m2: Optional[condecimal(ge=0, max_digits=16, decimal_places=2)] = None

class GranjaMini(ORMModel):
    granja_id: int
    nombre: str

class GranjaRead(GranjaBase):
    granja_id: int
    created_at: datetime
    updated_at: datetime


# ============================================================
# Estanque
# ============================================================

# Status permitido en DB: 'i','a','c','m'
EstanqueStatusChar = Literal['i', 'a', 'c', 'm']

class EstanqueBase(ORMModel):
    granja_id: int
    nombre: constr(strip_whitespace=True, min_length=1, max_length=120)
    superficie_m2: condecimal(gt=0, max_digits=16, decimal_places=2)
    status: EstanqueStatusChar = Field('i', description="i=Inactivo, a=Activo, c=Cerrado, m=Mantenimiento")
    sob_estanque_pct: condecimal(ge=0, le=100, max_digits=5, decimal_places=2) = Field(100)

    # Metadatos SOB opcionales
    sob_source: Optional[constr(strip_whitespace=True, max_length=10)] = None  # 'general'|'manual'|'reforecast' (app-level)
    sob_note: Optional[constr(strip_whitespace=True, max_length=255)] = None

class EstanqueCreate(EstanqueBase):
    pass

class EstanqueUpdate(ORMModel):
    granja_id: Optional[int] = None
    nombre: Optional[constr(strip_whitespace=True, min_length=1, max_length=120)] = None
    superficie_m2: Optional[condecimal(gt=0, max_digits=16, decimal_places=2)] = None
    status: Optional[EstanqueStatusChar] = None
    sob_estanque_pct: Optional[condecimal(ge=0, le=100, max_digits=5, decimal_places=2)] = None

    sob_source: Optional[constr(strip_whitespace=True, max_length=10)] = None
    sob_note: Optional[constr(strip_whitespace=True, max_length=255)] = None

class EstanqueMini(ORMModel):
    estanque_id: int
    nombre: str

class EstanqueRead(EstanqueBase):
    estanque_id: int
    created_at: datetime
    updated_at: datetime

    # Trazabilidad de cambios de SOB (opcionales en respuesta)
    sob_updated_at: Optional[datetime] = None
    sob_updated_by: Optional[int] = None          # id del usuario que actualizó
    sob_user: Optional[UsuarioMini] = None        # enriquecido si lo cargas en el servicio

    # Relación mínima para facilitar UI (opcional)
    granja: Optional[GranjaMini] = None
