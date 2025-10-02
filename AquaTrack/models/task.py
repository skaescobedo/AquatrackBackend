# models/task.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    BigInteger, DateTime, ForeignKey, String, Text, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.user import Usuario


class Tarea(Base):
    __tablename__ = "tarea"

    tarea_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    estado: Mapped[str] = mapped_column(
        String(1), nullable=False, server_default="p"
    )  # 'p' pendiente, 'c' completada, 'x' cancelada

    prioridad: Mapped[Optional[str]] = mapped_column(
        String(1), nullable=True
    )  # 'a' alta, 'm' media, 'b' baja

    asignado_a: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("usuario.usuario_id"), nullable=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("usuario.usuario_id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    )

    # Relaciones
    asignado: Mapped[Optional["Usuario"]] = relationship(
        "Usuario", foreign_keys=[asignado_a], back_populates="tareas_asignadas", lazy="joined"
    )
    creador: Mapped[Optional["Usuario"]] = relationship(
        "Usuario", foreign_keys=[created_by], back_populates="tareas_creadas", lazy="joined"
    )

    def __repr__(self) -> str:
        return f"<Tarea id={self.tarea_id} titulo={self.titulo!r} estado={self.estado}>"
