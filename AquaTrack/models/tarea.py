from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Text, Date, DateTime, Numeric, CHAR, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class Tarea(Base):
    __tablename__ = "tarea"

    tarea_id: Mapped[int] = mapped_column(primary_key=True)
    granja_id: Mapped[Optional[int]] = mapped_column(ForeignKey("granja.granja_id"))
    titulo: Mapped[str] = mapped_column(String(160), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    prioridad: Mapped[str] = mapped_column(CHAR(1), default="m", nullable=False)
    fecha_limite: Mapped[Optional[date]] = mapped_column(Date)
    tiempo_estimado_horas: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    estado: Mapped[str] = mapped_column(CHAR(1), default="p", nullable=False)
    tipo: Mapped[Optional[str]] = mapped_column(String(80))
    periodo_clave: Mapped[Optional[str]] = mapped_column(String(40))
    es_recurrente: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    granja: Mapped[Optional["Granja"]] = relationship(back_populates="tareas")
    creador: Mapped[Optional["Usuario"]] = relationship(back_populates="tareas_creadas")
