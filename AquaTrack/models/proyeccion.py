from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Enum, Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class Proyeccion(Base):
    __tablename__ = "proyeccion"

    proyeccion_id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo.ciclo_id"), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(1), default="b", nullable=False)  # b/p/r/x
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    creada_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.usuario_id"))
    source_type: Mapped[Optional[str]] = mapped_column(Enum("auto", "archivo", "reforecast", name="proy_source_type"))
    source_ref: Mapped[Optional[str]] = mapped_column(String(120))
    parent_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("proyeccion.proyeccion_id"))
    sob_final_objetivo_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    siembra_ventana_inicio: Mapped[Optional[datetime]] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    ciclo: Mapped["Ciclo"] = relationship(back_populates="proyecciones")
    creador: Mapped[Optional["Usuario"]] = relationship(back_populates="proyecciones_creadas")
    parent: Mapped[Optional["Proyeccion"]] = relationship(remote_side="Proyeccion.proyeccion_id")

    lineas: Mapped[List["ProyeccionLinea"]] = relationship(back_populates="proyeccion", cascade="all, delete-orphan")
    archivos: Mapped[List["ArchivoProyeccion"]] = relationship(back_populates="proyeccion", cascade="all, delete-orphan")
    plan_cosechas: Mapped[Optional["PlanCosechas"]] = relationship(back_populates="proyeccion", uselist=False)
