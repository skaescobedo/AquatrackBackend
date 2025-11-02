# schemas/task.py
from __future__ import annotations

from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator, computed_field
from typing import Literal


# ============================================================================
# DTOs de Usuario (simplificados para nested objects)
# ============================================================================

class UsuarioBasicOut(BaseModel):
    """Usuario simplificado para asignaciones"""
    usuario_id: int
    nombre: str
    apellido1: str
    email: str

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def nombre_completo(self) -> str:
        """Nombre completo (nombre + apellido1)"""
        return f"{self.nombre} {self.apellido1}"


# ============================================================================
# DTOs de Entrada (Create/Update)
# ============================================================================

class TareaCreate(BaseModel):
    """
    Crear nueva tarea.

    NOTA: granja_id NO se incluye aquí porque SIEMPRE viene del path.
    El router lo asigna automáticamente.
    """
    ciclo_id: int | None = None
    estanque_id: int | None = None
    titulo: str = Field(..., min_length=1, max_length=160)
    descripcion: str | None = Field(None, max_length=500)
    prioridad: Literal["b", "m", "a"] = "m"
    fecha_limite: date | None = None
    tiempo_estimado_horas: float | None = Field(None, ge=0)
    tipo: str | None = Field(None, max_length=80)
    es_recurrente: bool = False
    asignados_ids: list[int] = Field(default_factory=list)

    @field_validator("ciclo_id", "estanque_id")
    @classmethod
    def convert_zero_to_none(cls, v: int | None) -> int | None:
        """Convertir 0 a None (para IDs opcionales)"""
        if v == 0:
            return None
        return v

    @field_validator("titulo")
    @classmethod
    def validate_titulo(cls, v: str) -> str:
        """Validar que el título no esté vacío después de strip"""
        if not v.strip():
            raise ValueError("El título no puede estar vacío")
        return v.strip()

    @field_validator("descripcion")
    @classmethod
    def validate_descripcion(cls, v: str | None) -> str | None:
        """Validar longitud de descripción y hacer strip"""
        if v is not None:
            v = v.strip()
            if len(v) > 500:
                raise ValueError("La descripción no puede exceder 500 caracteres")
            return v if v else None
        return None

    @field_validator("asignados_ids")
    @classmethod
    def validate_asignados_ids(cls, v: list[int]) -> list[int]:
        """Validar que no haya duplicados en asignados_ids y filtrar ceros"""
        # Filtrar ceros
        v = [id for id in v if id != 0]
        # Validar duplicados
        if len(v) != len(set(v)):
            raise ValueError("No puede haber usuario_ids duplicados en asignados_ids")
        return v


class TareaUpdate(BaseModel):
    """Actualizar tarea existente"""
    titulo: str | None = Field(None, min_length=1, max_length=160)
    descripcion: str | None = Field(None, max_length=500)
    prioridad: Literal["b", "m", "a"] | None = None
    fecha_limite: date | None = None
    tiempo_estimado_horas: float | None = Field(None, ge=0)
    progreso_pct: float | None = Field(None, ge=0, le=100)
    status: Literal["p", "e", "c", "x"] | None = None
    tipo: str | None = Field(None, max_length=80)
    es_recurrente: bool | None = None
    asignados_ids: list[int] | None = None

    @field_validator("titulo")
    @classmethod
    def validate_titulo(cls, v: str | None) -> str | None:
        """Validar que el título no esté vacío después de strip"""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("El título no puede estar vacío")
            return v
        return None

    @field_validator("descripcion")
    @classmethod
    def validate_descripcion(cls, v: str | None) -> str | None:
        """Validar longitud de descripción y hacer strip"""
        if v is not None:
            v = v.strip()
            if len(v) > 500:
                raise ValueError("La descripción no puede exceder 500 caracteres")
            return v if v else None
        return None

    @field_validator("asignados_ids")
    @classmethod
    def validate_asignados_ids(cls, v: list[int] | None) -> list[int] | None:
        """Validar que no haya duplicados en asignados_ids"""
        if v is not None and len(v) != len(set(v)):
            raise ValueError("No puede haber usuario_ids duplicados en asignados_ids")
        return v


class TareaUpdateStatus(BaseModel):
    """Actualizar solo status y progreso (operación rápida)"""
    status: Literal["p", "e", "c", "x"]
    progreso_pct: float | None = Field(None, ge=0, le=100)

    @field_validator("progreso_pct")
    @classmethod
    def validate_progreso_pct(cls, v: float | None) -> float | None:
        """Validar rango de progreso"""
        if v is not None and (v < 0 or v > 100):
            raise ValueError("El progreso debe estar entre 0 y 100")
        return v


# ============================================================================
# DTOs de Salida (Response)
# ============================================================================

class TareaAsignacionOut(BaseModel):
    """Asignación individual"""
    asignacion_id: int
    usuario: UsuarioBasicOut
    created_at: datetime

    model_config = {"from_attributes": True}


class TareaOut(BaseModel):
    """Tarea completa con asignaciones"""
    tarea_id: int
    granja_id: int | None
    ciclo_id: int | None
    estanque_id: int | None
    titulo: str
    descripcion: str | None
    prioridad: str
    status: str
    tipo: str | None
    fecha_limite: date | None
    tiempo_estimado_horas: float | None
    progreso_pct: float
    es_recurrente: bool
    created_by: int
    creador: UsuarioBasicOut
    asignaciones: list[TareaAsignacionOut]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def responsables_nombres(self) -> list[str]:
        """Obtener nombres completos de los responsables"""
        if self.asignaciones:
            return [asig.usuario.nombre_completo for asig in self.asignaciones]
        return [self.creador.nombre_completo]

    @computed_field
    @property
    def dias_restantes(self) -> int | None:
        """Calcular días restantes hasta la fecha límite"""
        if self.fecha_limite is None:
            return None
        from utils.datetime_utils import today_mazatlan
        hoy = today_mazatlan()
        delta = (self.fecha_limite - hoy).days
        return delta

    @computed_field
    @property
    def is_vencida(self) -> bool:
        """Verificar si la tarea está vencida"""
        if self.fecha_limite is None:
            return False
        if self.status in ["c", "x"]:
            return False
        from utils.datetime_utils import today_mazatlan
        return self.fecha_limite < today_mazatlan()


class TareaListOut(BaseModel):
    """Versión simplificada para listas"""
    tarea_id: int
    titulo: str
    prioridad: str
    status: str
    tipo: str | None
    fecha_limite: date | None
    progreso_pct: float
    created_by: int
    asignados_count: int
    responsables_nombres: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_tarea(cls, tarea) -> "TareaListOut":
        """Constructor personalizado desde modelo Tarea"""
        # Calcular responsables con nombre completo
        if tarea.asignaciones:
            responsables = [asig.usuario.nombre_completo for asig in tarea.asignaciones]
            asignados_count = len(tarea.asignaciones)
        else:
            responsables = [tarea.creador.nombre_completo]
            asignados_count = 0

        return cls(
            tarea_id=tarea.tarea_id,
            titulo=tarea.titulo,
            prioridad=tarea.prioridad,
            status=tarea.status,
            tipo=tarea.tipo,
            fecha_limite=tarea.fecha_limite,
            progreso_pct=float(tarea.progreso_pct),
            created_by=tarea.created_by,
            asignados_count=asignados_count,
            responsables_nombres=responsables,
            created_at=tarea.created_at
        )