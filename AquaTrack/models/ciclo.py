from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import String, Text, Date, DateTime, ForeignKey, Enum as SAEnum, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from enums.enums import CicloEstadoEnum


class Ciclo(Base):
    __tablename__ = "ciclo"

    ciclo_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    granja_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("granja.granja_id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin_planificada: Mapped[Optional[date]] = mapped_column(Date)
    fecha_cierre_real: Mapped[Optional[date]] = mapped_column(Date)
    # BD usa CHAR(1) con CHECK; mapeamos Enum Python a varchar(1) (no ENUM) para no tocar BD
    estado: Mapped[CicloEstadoEnum] = mapped_column(
        SAEnum(CicloEstadoEnum, native_enum=False, length=1, name="ciclo_estado_enum"),
        server_default=text("'a'"),
        nullable=False,
    )
    observaciones: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )

    granja: Mapped["Granja"] = relationship(back_populates="ciclos")
    resumen: Mapped[Optional["CicloResumen"]] = relationship(back_populates="ciclo", uselist=False)

    proyecciones: Mapped[List["Proyeccion"]] = relationship(back_populates="ciclo", lazy="selectin")
    siembra_plan: Mapped[Optional["SiembraPlan"]] = relationship(back_populates="ciclo", uselist=False)
    plan_cosechas: Mapped[Optional["PlanCosechas"]] = relationship(back_populates="ciclo", uselist=False)

    biometrias: Mapped[List["Biometria"]] = relationship(back_populates="ciclo", lazy="selectin")
    sob_logs: Mapped[List["SobCambioLog"]] = relationship(back_populates="ciclo", lazy="selectin")
