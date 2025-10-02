# schemas/projection.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Literal, List

from pydantic import Field, condecimal, conint, constr

from .shared import ORMModel
from .user import UsuarioMini
from .cycle import CicloMini


# ============================================================
# Literales / constantes
# ============================================================

# Proyeccion.status en DB: 'b','p','r','x'
ProyeccionStatusChar = Literal['b', 'p', 'r', 'x']

# Proyeccion.source_type en DB (string corto)
ProyeccionSourceLiteral = Literal['auto', 'archivo', 'reforecast']


# ============================================================
# Proyeccion
# ============================================================

class ProyeccionBase(ORMModel):
    ciclo_id: int
    version: constr(strip_whitespace=True, min_length=1, max_length=20)
    descripcion: Optional[constr(strip_whitespace=True, max_length=255)] = None
    status: ProyeccionStatusChar = Field('b', description="b=borrador, p=publicada, r=reforecast, x=cancelada")
    is_current: bool = Field(False, description="Marca esta proyección como la vigente del ciclo.")

    published_at: Optional[datetime] = None
    creada_por: Optional[int] = Field(default=None, description="Usuario creador (opcional).")

    source_type: Optional[ProyeccionSourceLiteral] = None
    source_ref: Optional[constr(strip_whitespace=True, max_length=120)] = None
    parent_version_id: Optional[int] = None

    siembra_ventana_inicio: Optional[date] = None

class ProyeccionCreate(ProyeccionBase):
    pass

class ProyeccionUpdate(ORMModel):
    ciclo_id: Optional[int] = None
    version: Optional[constr(strip_whitespace=True, min_length=1, max_length=20)] = None
    descripcion: Optional[constr(strip_whitespace=True, max_length=255)] = None
    status: Optional[ProyeccionStatusChar] = None
    is_current: Optional[bool] = None

    published_at: Optional[datetime] = None
    creada_por: Optional[int] = None

    source_type: Optional[ProyeccionSourceLiteral] = None
    source_ref: Optional[constr(strip_whitespace=True, max_length=120)] = None
    parent_version_id: Optional[int] = None

    siembra_ventana_inicio: Optional[date] = None

class ProyeccionMini(ORMModel):
    proyeccion_id: int
    version: str
    status: ProyeccionStatusChar
    is_current: bool

class ProyeccionRead(ProyeccionBase):
    proyeccion_id: int
    created_at: datetime
    updated_at: datetime

    # Enriquecimientos opcionales
    ciclo: Optional[CicloMini] = None
    creador: Optional[UsuarioMini] = None
    parent: Optional[ProyeccionMini] = None

    # Cargas relacionadas (opcionales)
    lineas: List["ProyeccionLineaRead"] = Field(default_factory=list)
    parametros: Optional["ParametroCicloVersionRead"] = None

    # Nota: si luego quieres exponer plan de cosechas o archivos vinculados,
    # puedes añadir campos como ids o minis aquí para no crear dependencias circulares.


# ============================================================
# ProyeccionLinea
# ============================================================

class ProyeccionLineaBase(ORMModel):
    proyeccion_id: int

    edad_dias: conint(ge=0)
    semana_idx: conint(ge=0)
    fecha_plan: date

    pp_g: condecimal(ge=0, max_digits=10, decimal_places=3)               # Numeric(7,3)
    incremento_g_sem: Optional[condecimal(max_digits=10, decimal_places=3)] = None  # puede ser negativo; quita 'ge=0'
    sob_pct_linea: condecimal(ge=0, le=100, max_digits=5, decimal_places=2)

    cosecha_flag: bool = Field(False)
    retiro_org_m2: Optional[condecimal(ge=0, max_digits=16, decimal_places=4)] = None
    nota: Optional[constr(strip_whitespace=True, max_length=255)] = None

class ProyeccionLineaCreate(ProyeccionLineaBase):
    pass

class ProyeccionLineaUpdate(ORMModel):
    proyeccion_id: Optional[int] = None

    edad_dias: Optional[conint(ge=0)] = None
    semana_idx: Optional[conint(ge=0)] = None
    fecha_plan: Optional[date] = None

    pp_g: Optional[condecimal(ge=0, max_digits=10, decimal_places=3)] = None
    incremento_g_sem: Optional[condecimal(max_digits=10, decimal_places=3)] = None
    sob_pct_linea: Optional[condecimal(ge=0, le=100, max_digits=5, decimal_places=2)] = None

    cosecha_flag: Optional[bool] = None
    retiro_org_m2: Optional[condecimal(ge=0, max_digits=16, decimal_places=4)] = None
    nota: Optional[constr(strip_whitespace=True, max_length=255)] = None

class ProyeccionLineaRead(ProyeccionLineaBase):
    proyeccion_linea_id: int


# ============================================================
# ParametroCicloVersion (1:1 con Proyeccion, ligado a un Ciclo)
# ============================================================

class ParametroCicloVersionBase(ORMModel):
    ciclo_id: int
    proyeccion_id: int

    sob_actual_pct_snapshot: condecimal(ge=0, le=100, max_digits=5, decimal_places=2)
    sob_final_objetivo_pct: condecimal(ge=0, le=100, max_digits=5, decimal_places=2)

    nota: Optional[constr(strip_whitespace=True, max_length=255)] = None
    updated_by: Optional[int] = None

class ParametroCicloVersionCreate(ParametroCicloVersionBase):
    pass

class ParametroCicloVersionUpdate(ORMModel):
    ciclo_id: Optional[int] = None
    proyeccion_id: Optional[int] = None

    sob_actual_pct_snapshot: Optional[condecimal(ge=0, le=100, max_digits=5, decimal_places=2)] = None
    sob_final_objetivo_pct: Optional[condecimal(ge=0, le=100, max_digits=5, decimal_places=2)] = None

    nota: Optional[constr(strip_whitespace=True, max_length=255)] = None
    updated_by: Optional[int] = None

class ParametroCicloVersionRead(ParametroCicloVersionBase):
    parametro_ciclo_version_id: int
    created_at: datetime
    updated_at: datetime

    # Enriquecimientos opcionales
    ciclo: Optional[CicloMini] = None
    proyeccion: Optional[ProyeccionMini] = None
    usuario: Optional[UsuarioMini] = None
