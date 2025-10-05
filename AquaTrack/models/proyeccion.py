from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import String, DateTime, ForeignKey, Enum as SAEnum, Date, text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL, TINYINT, ENUM as MYSQL_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from enums.enums import ProyeccionStatusEnum, ProyeccionSourceEnum


class Proyeccion(Base):
    __tablename__ = "proyeccion"

    proyeccion_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    ciclo_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("ciclo.ciclo_id"), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(String(255))
    # CHAR(1) en BD + CHECK; usamos Enum python sin ENUM nativo
    status: Mapped[ProyeccionStatusEnum] = mapped_column(
        SAEnum(ProyeccionStatusEnum, native_enum=False, length=1, name="proyeccion_status_enum"),
        server_default=text("'b'"),
        nullable=False,
    )
    is_current: Mapped[bool] = mapped_column(TINYINT(1), server_default=text("0"), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    creada_por: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True), ForeignKey("usuario.usuario_id"))
    # La BD tiene ENUM('auto','archivo','reforecast')
    source_type: Mapped[Optional[ProyeccionSourceEnum]] = mapped_column(
        SAEnum(ProyeccionSourceEnum, name="proy_source_type", native_enum=True)
    )
    source_ref: Mapped[Optional[str]] = mapped_column(String(120))
    parent_version_id: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True), ForeignKey("proyeccion.proyeccion_id"))
    sob_final_objetivo_pct: Mapped[Optional[float]] = mapped_column(DECIMAL(5, 2))
    siembra_ventana_inicio: Mapped[Optional[date]] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )

    ciclo: Mapped["Ciclo"] = relationship(back_populates="proyecciones")
    creador: Mapped[Optional["Usuario"]] = relationship(
        back_populates="proyecciones_creadas",
        foreign_keys=[creada_por],
    )
    parent: Mapped[Optional["Proyeccion"]] = relationship(remote_side="Proyeccion.proyeccion_id")

    lineas: Mapped[List["ProyeccionLinea"]] = relationship(back_populates="proyeccion", cascade="all, delete-orphan", lazy="selectin")
    archivos: Mapped[List["ArchivoProyeccion"]] = relationship(back_populates="proyeccion", cascade="all, delete-orphan", lazy="selectin")
    plan_cosechas: Mapped[Optional["PlanCosechas"]] = relationship(back_populates="proyeccion", uselist=False)
