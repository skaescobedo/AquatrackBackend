# schemas/harvest.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Literal, List

from pydantic import Field, condecimal, constr, conint

from .shared import ORMModel
from .user import UsuarioMini
from .cycle import CicloMini
from .projection import ProyeccionMini
from .farm import EstanqueMini


# ============================================================
# Literales / Constantes
# ============================================================

# Estados: Plan/Ola permiten ('p','r','x'); Estanque agrega 'c' confirmado
EstadoCosechaOlaChar = Literal['p', 'r', 'x']       # para CosechaOla
EstadoCosechaEstanqueChar = Literal['p', 'r', 'c', 'x']  # para CosechaEstanque
TipoCosechaChar = Literal['p', 'f']  # p=parcial, f=final


# ============================================================
# PlanCosechas
# ============================================================

class PlanCosechasBase(ORMModel):
    ciclo_id: int
    proyeccion_id: int

    nombre: constr(strip_whitespace=True, min_length=1, max_length=120)
    fecha_inicio_plan: date
    fecha_fin_plan: date
    nota_operativa: Optional[constr(strip_whitespace=True, max_length=255)] = None

    created_by: Optional[int] = Field(default=None, description="Usuario creador (opcional).")

class PlanCosechasCreate(PlanCosechasBase):
    pass

class PlanCosechasUpdate(ORMModel):
    ciclo_id: Optional[int] = None
    proyeccion_id: Optional[int] = None
    nombre: Optional[constr(strip_whitespace=True, min_length=1, max_length=120)] = None
    fecha_inicio_plan: Optional[date] = None
    fecha_fin_plan: Optional[date] = None
    nota_operativa: Optional[constr(strip_whitespace=True, max_length=255)] = None
    created_by: Optional[int] = None

class PlanCosechasMini(ORMModel):
    plan_cosechas_id: int
    nombre: str

class PlanCosechasRead(PlanCosechasBase):
    plan_cosechas_id: int
    created_at: datetime
    updated_at: datetime

    # Enriquecimientos opcionales
    ciclo: Optional[CicloMini] = None
    proyeccion: Optional[ProyeccionMini] = None
    creador: Optional[UsuarioMini] = None

    # Cargas relacionadas
    olas: List["CosechaOlaRead"] = Field(default_factory=list)
    # Si quieres exponer archivos vinculados más adelante, puedes crear un esquema mini aquí
    # y mapear desde ArchivoPlanCosechas en el servicio.


# ============================================================
# CosechaOla
# ============================================================

class CosechaOlaBase(ORMModel):
    plan_cosechas_id: int

    nombre: constr(strip_whitespace=True, min_length=1, max_length=120)
    tipo: TipoCosechaChar = Field(..., description="p=parcial, f=final")

    ventana_inicio: date
    ventana_fin: date

    objetivo_retiro_org_m2: Optional[condecimal(ge=0, max_digits=16, decimal_places=4)] = None
    estado: EstadoCosechaOlaChar = Field('p', description="p=planeada, r=realizada, x=cancelada")
    orden: Optional[conint(ge=0)] = None
    notas: Optional[constr(strip_whitespace=True, max_length=255)] = None

    created_by: Optional[int] = Field(default=None, description="Usuario creador (opcional).")

class CosechaOlaCreate(CosechaOlaBase):
    pass

class CosechaOlaUpdate(ORMModel):
    plan_cosechas_id: Optional[int] = None
    nombre: Optional[constr(strip_whitespace=True, min_length=1, max_length=120)] = None
    tipo: Optional[TipoCosechaChar] = None
    ventana_inicio: Optional[date] = None
    ventana_fin: Optional[date] = None
    objetivo_retiro_org_m2: Optional[condecimal(ge=0, max_digits=16, decimal_places=4)] = None
    estado: Optional[EstadoCosechaOlaChar] = None
    orden: Optional[conint(ge=0)] = None
    notas: Optional[constr(strip_whitespace=True, max_length=255)] = None
    created_by: Optional[int] = None

class CosechaOlaMini(ORMModel):
    cosecha_ola_id: int
    nombre: str
    estado: EstadoCosechaOlaChar

class CosechaOlaRead(CosechaOlaBase):
    cosecha_ola_id: int
    created_at: datetime
    updated_at: datetime

    plan: Optional[PlanCosechasMini] = None
    creador: Optional[UsuarioMini] = None

    # Hijos
    cosechas: List["CosechaEstanqueRead"] = Field(default_factory=list)


# ============================================================
# CosechaEstanque
# ============================================================

class CosechaEstanqueBase(ORMModel):
    estanque_id: int
    cosecha_ola_id: int

    tipo: TipoCosechaChar = Field(..., description="p=parcial, f=final")
    estado: EstadoCosechaEstanqueChar = Field('p', description="p=planeada, r=realizada, c=confirmada, x=cancelada")

    fecha_cosecha: date

    pp_g: Optional[condecimal(ge=0, max_digits=10, decimal_places=3)] = None    # Numeric(7,3)
    biomasa_kg: Optional[condecimal(ge=0, max_digits=17, decimal_places=3)] = None  # Numeric(14,3)
    densidad_retirada_org_m2: Optional[condecimal(ge=0, max_digits=16, decimal_places=4)] = None

    notas: Optional[constr(strip_whitespace=True, max_length=255)] = None

    # Confirmación / auditoría
    confirmado_por: Optional[int] = None
    confirmado_event_at: Optional[datetime] = None

    created_by: Optional[int] = None

class CosechaEstanqueCreate(CosechaEstanqueBase):
    pass

class CosechaEstanqueUpdate(ORMModel):
    estanque_id: Optional[int] = None
    cosecha_ola_id: Optional[int] = None
    tipo: Optional[TipoCosechaChar] = None
    estado: Optional[EstadoCosechaEstanqueChar] = None
    fecha_cosecha: Optional[date] = None
    pp_g: Optional[condecimal(ge=0, max_digits=10, decimal_places=3)] = None
    biomasa_kg: Optional[condecimal(ge=0, max_digits=17, decimal_places=3)] = None
    densidad_retirada_org_m2: Optional[condecimal(ge=0, max_digits=16, decimal_places=4)] = None
    notas: Optional[constr(strip_whitespace=True, max_length=255)] = None
    confirmado_por: Optional[int] = None
    confirmado_event_at: Optional[datetime] = None
    created_by: Optional[int] = None

class CosechaEstanqueMini(ORMModel):
    cosecha_estanque_id: int
    tipo: TipoCosechaChar
    estado: EstadoCosechaEstanqueChar
    fecha_cosecha: date

class CosechaEstanqueRead(CosechaEstanqueBase):
    cosecha_estanque_id: int
    created_at: datetime
    updated_at: datetime

    # Enriquecimientos opcionales
    ola: Optional[CosechaOlaMini] = None
    estanque: Optional[EstanqueMini] = None
    creador: Optional[UsuarioMini] = None
    confirmador: Optional[UsuarioMini] = None

    # Historial
    fecha_logs: List["CosechaFechaLogRead"] = Field(default_factory=list)


# ============================================================
# CosechaFechaLog
# ============================================================

class CosechaFechaLogBase(ORMModel):
    cosecha_estanque_id: int
    fecha_anterior: date
    fecha_nueva: date
    motivo: Optional[constr(strip_whitespace=True, max_length=255)] = None
    changed_by: int

class CosechaFechaLogCreate(CosechaFechaLogBase):
    pass

class CosechaFechaLogRead(CosechaFechaLogBase):
    cosecha_fecha_log_id: int
    changed_at: datetime

    # Enriquecimiento opcional
    usuario: Optional[UsuarioMini] = None
