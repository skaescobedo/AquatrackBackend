# models/task.py
from __future__ import annotations

from datetime import datetime, date
from sqlalchemy import (
    BigInteger, Date, DateTime, ForeignKey, String, Numeric, CHAR, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum

from utils.db import Base
from utils.datetime_utils import now_mazatlan


class TaskStatus(str, Enum):
    """Estados de la tarea"""
    PENDIENTE = "p"
    EN_PROGRESO = "e"
    COMPLETADA = "c"
    CANCELADA = "x"

    @classmethod
    def _missing_(cls, value):
        """Permitir que SQLAlchemy mapee valores independientemente del case"""
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None


class TaskPriority(str, Enum):
    """Prioridades de la tarea"""
    BAJA = "b"
    MEDIA = "m"
    ALTA = "a"

    @classmethod
    def _missing_(cls, value):
        """Permitir que SQLAlchemy mapee valores independientemente del case"""
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None


class Tarea(Base):
    """
    Modelo de Tarea para gestión de actividades operativas.

    Características:
    - Asignación múltiple vía tabla tarea_asignacion (1 o N usuarios)
    - Si no hay asignaciones, created_by es el responsable por defecto
    - Vinculación opcional con ciclo/estanque
    - Progreso manual (0-100%)
    - Flag de recurrencia para duplicación
    """
    __tablename__ = "tarea"

    tarea_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    granja_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("granja.granja_id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    ciclo_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ciclo.ciclo_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    estanque_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("estanque.estanque_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Información básica
    titulo: Mapped[str] = mapped_column(String(160), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500))

    # Clasificación
    prioridad: Mapped[str] = mapped_column(CHAR(1), default="m", nullable=False)  # b/m/a
    status: Mapped[str] = mapped_column(CHAR(1), default="p", nullable=False, index=True)  # p/e/c/x
    tipo: Mapped[str | None] = mapped_column(String(80))  # "Biometry", "Mantenimiento", etc.

    # Temporalidad
    fecha_limite: Mapped[date | None] = mapped_column(Date, index=True)
    tiempo_estimado_horas: Mapped[float | None] = mapped_column(Numeric(6, 2))

    # Progreso
    progreso_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0, nullable=False)

    # Flags
    es_recurrente: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Creador (siempre presente)
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuario.usuario_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Auditoría
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=now_mazatlan,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=now_mazatlan,
        onupdate=now_mazatlan,
        nullable=False
    )

    # Relationships
    granja: Mapped["Granja"] = relationship("Granja", foreign_keys=[granja_id])
    ciclo: Mapped["Ciclo | None"] = relationship("Ciclo", foreign_keys=[ciclo_id])
    estanque: Mapped["Estanque | None"] = relationship("Estanque", foreign_keys=[estanque_id])
    creador: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[created_by])

    asignaciones: Mapped[list["TareaAsignacion"]] = relationship(
        "TareaAsignacion",
        back_populates="tarea",
        cascade="all, delete-orphan"
    )


class TareaAsignacion(Base):
    """
    Modelo de asignaciones para tareas.

    Maneja TODAS las asignaciones (1 o múltiples usuarios).
    Si la tarea no tiene asignaciones, el creador (created_by) es
    el responsable por defecto (lógica en service).

    Características:
    - UNIQUE constraint (tarea_id, usuario_id) previene duplicados
    - CASCADE delete: si se elimina tarea o usuario, se elimina asignación
    - Cualquier usuario asignado puede completar la tarea
    """
    __tablename__ = "tarea_asignacion"

    asignacion_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tarea_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tarea.tarea_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    usuario_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuario.usuario_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=now_mazatlan,
        nullable=False
    )

    # Relationships
    tarea: Mapped["Tarea"] = relationship("Tarea", back_populates="asignaciones")
    usuario: Mapped["Usuario"] = relationship("Usuario")