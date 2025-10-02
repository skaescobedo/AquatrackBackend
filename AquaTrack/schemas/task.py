# schemas/task.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import Field, constr

from .shared import ORMModel
from .user import UsuarioMini


# ============================================================
# Literales / constantes
# ============================================================

# Estado en DB: 'p' pendiente, 'c' completada, 'x' cancelada
TareaEstadoChar = Literal['p', 'c', 'x']

# Prioridad opcional: 'a' alta, 'm' media, 'b' baja
TareaPrioridadChar = Literal['a', 'm', 'b']


# ============================================================
# Tarea
# ============================================================

class TareaBase(ORMModel):
    titulo: constr(strip_whitespace=True, min_length=1, max_length=200)
    descripcion: Optional[constr(strip_whitespace=True, max_length=2000)] = None  # Text en DB; límite razonable en API

    estado: TareaEstadoChar = Field('p', description="p=pendiente, c=completada, x=cancelada")
    prioridad: Optional[TareaPrioridadChar] = Field(default=None, description="a=alta, m=media, b=baja")

    asignado_a: Optional[int] = Field(default=None, description="Usuario asignado (opcional).")
    created_by: Optional[int] = Field(default=None, description="Creador (opcional).")

class TareaCreate(TareaBase):
    pass

class TareaUpdate(ORMModel):
    titulo: Optional[constr(strip_whitespace=True, min_length=1, max_length=200)] = None
    descripcion: Optional[constr(strip_whitespace=True, max_length=2000)] = None

    estado: Optional[TareaEstadoChar] = None
    prioridad: Optional[TareaPrioridadChar] = None

    asignado_a: Optional[int] = None
    created_by: Optional[int] = None

class TareaMini(ORMModel):
    tarea_id: int
    titulo: str
    estado: TareaEstadoChar

class TareaRead(TareaBase):
    tarea_id: int
    created_at: datetime
    updated_at: datetime

    # Enriquecimientos opcionales (si cargas relaciones en la query)
    asignado: Optional[UsuarioMini] = None
    creador: Optional[UsuarioMini] = None
