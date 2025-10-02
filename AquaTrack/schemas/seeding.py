# schemas/seeding.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Literal, List

from pydantic import Field, condecimal, constr

from .shared import ORMModel
from .user import UsuarioMini
from .farm import EstanqueMini
from .cycle import CicloMini


# ============================================================
# Tipos/constantes
# ============================================================

# Estados permitidos en DB: 'p' (planeada), 'f' (finalizada)
EstadoSiembraChar = Literal['p', 'f']


# ============================================================
# SiembraPlan
# ============================================================

class SiembraPlanBase(ORMModel):
    ciclo_id: int
    ventana_inicio: date
    ventana_fin: date
    # Numeric(12,4) y Numeric(7,3) en DB
    densidad_org_m2: condecimal(ge=0, max_digits=16, decimal_places=4)
    talla_inicial_g: condecimal(ge=0, max_digits=10, decimal_places=3)
    observaciones: Optional[constr(strip_whitespace=True, max_length=1000)] = None

class SiembraPlanCreate(SiembraPlanBase):
    # Si no lo estableces desde la API, tu servicio puede tomar el usuario actual
    created_by: Optional[int] = Field(default=None, description="ID del usuario que crea el plan (opcional).")

class SiembraPlanUpdate(ORMModel):
    ciclo_id: Optional[int] = None
    ventana_inicio: Optional[date] = None
    ventana_fin: Optional[date] = None
    densidad_org_m2: Optional[condecimal(ge=0, max_digits=16, decimal_places=4)] = None
    talla_inicial_g: Optional[condecimal(ge=0, max_digits=10, decimal_places=3)] = None
    observaciones: Optional[constr(strip_whitespace=True, max_length=1000)] = None

class SiembraPlanRead(SiembraPlanBase):
    siembra_plan_id: int
    created_at: datetime
    updated_at: datetime
    # Enriquecimientos opcionales
    ciclo: Optional[CicloMini] = None
    creador: Optional[UsuarioMini] = None


# ============================================================
# SiembraEstanque
# ============================================================

class SiembraEstanqueBase(ORMModel):
    siembra_plan_id: int
    estanque_id: int
    estado: EstadoSiembraChar = Field('p', description="p=planeada, f=finalizada")

    fecha_tentativa: Optional[date] = None
    fecha_siembra: Optional[date] = None

    lote: Optional[constr(strip_whitespace=True, max_length=80)] = None
    densidad_override_org_m2: Optional[condecimal(ge=0, max_digits=16, decimal_places=4)] = None
    talla_inicial_override_g: Optional[condecimal(ge=0, max_digits=10, decimal_places=3)] = None

class SiembraEstanqueCreate(SiembraEstanqueBase):
    created_by: Optional[int] = Field(default=None, description="ID del usuario que crea el registro (opcional).")

class SiembraEstanqueUpdate(ORMModel):
    siembra_plan_id: Optional[int] = None
    estanque_id: Optional[int] = None
    estado: Optional[EstadoSiembraChar] = None

    fecha_tentativa: Optional[date] = None
    fecha_siembra: Optional[date] = None

    lote: Optional[constr(strip_whitespace=True, max_length=80)] = None
    densidad_override_org_m2: Optional[condecimal(ge=0, max_digits=16, decimal_places=4)] = None
    talla_inicial_override_g: Optional[condecimal(ge=0, max_digits=10, decimal_places=3)] = None

class SiembraEstanqueRead(SiembraEstanqueBase):
    siembra_estanque_id: int
    created_at: datetime
    updated_at: datetime

    # Enriquecimientos opcionales
    creador: Optional[UsuarioMini] = None
    estanque: Optional[EstanqueMini] = None

    # Historial de cambios de fecha (si deseas devolverlos en lecturas detalladas)
    fecha_logs: List["SiembraFechaLogRead"] = Field(default_factory=list)


# ============================================================
# SiembraFechaLog
# ============================================================

class SiembraFechaLogBase(ORMModel):
    siembra_estanque_id: int
    fecha_anterior: date
    fecha_nueva: date
    motivo: Optional[constr(strip_whitespace=True, max_length=255)] = None
    changed_by: int

class SiembraFechaLogCreate(SiembraFechaLogBase):
    pass

class SiembraFechaLogRead(SiembraFechaLogBase):
    siembra_fecha_log_id: int
    changed_at: datetime
    # Enriquecimiento opcional
    usuario: Optional[UsuarioMini] = None
