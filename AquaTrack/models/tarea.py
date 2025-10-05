from __future__ import annotations
from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, Text, Date, DateTime, Enum as SAEnum, ForeignKey, text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from enums.enums import TareaPrioridadEnum, TareaEstadoEnum


class Tarea(Base):
    __tablename__ = "tarea"

    tarea_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    granja_id: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True), ForeignKey("granja.granja_id"))
    titulo: Mapped[str] = mapped_column(String(160), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    prioridad: Mapped[TareaPrioridadEnum] = mapped_column(
        SAEnum(TareaPrioridadEnum, native_enum=False, length=1, name="tarea_prioridad_enum"),
        server_default=text("'m'"),
        nullable=False,
    )
    fecha_limite: Mapped[Optional[date]] = mapped_column(Date)
    tiempo_estimado_horas: Mapped[Optional[float]] = mapped_column(DECIMAL(6, 2))
    estado: Mapped[TareaEstadoEnum] = mapped_column(
        SAEnum(TareaEstadoEnum, native_enum=False, length=1, name="tarea_estado_enum"),
        server_default=text("'p'"),
        nullable=False,
    )
    tipo: Mapped[Optional[str]] = mapped_column(String(80))
    periodo_clave: Mapped[Optional[str]] = mapped_column(String(40))
    es_recurrente: Mapped[bool] = mapped_column(TINYINT(1), server_default=text("0"), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True), ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )

    granja: Mapped[Optional["Granja"]] = relationship(back_populates="tareas")
    creador: Mapped[Optional["Usuario"]] = relationship(
        back_populates="tareas_creadas",
        foreign_keys=[created_by],
    )
