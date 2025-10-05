from __future__ import annotations
from datetime import date
from typing import Optional

from sqlalchemy import Date, String, ForeignKey, text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


class ProyeccionLinea(Base):
    __tablename__ = "proyeccion_linea"

    proyeccion_linea_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    proyeccion_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("proyeccion.proyeccion_id"), nullable=False)

    edad_dias: Mapped[int] = mapped_column(nullable=False)
    semana_idx: Mapped[int] = mapped_column(nullable=False)
    fecha_plan: Mapped[date] = mapped_column(Date, nullable=False)
    pp_g: Mapped[float] = mapped_column(DECIMAL(7, 3), nullable=False)
    sob_pct_linea: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)

    incremento_g_sem: Mapped[Optional[float]] = mapped_column(DECIMAL(7, 3))
    cosecha_flag: Mapped[bool] = mapped_column(TINYINT(1), server_default=text("0"), nullable=False)
    retiro_org_m2: Mapped[Optional[float]] = mapped_column(DECIMAL(12, 4))
    nota: Mapped[Optional[str]] = mapped_column(String(255))

    proyeccion: Mapped["Proyeccion"] = relationship(back_populates="lineas")
