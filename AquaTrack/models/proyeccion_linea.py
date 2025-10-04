from __future__ import annotations
from datetime import date
from typing import Optional
from sqlalchemy import Integer, Date, Numeric, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class ProyeccionLinea(Base):
    __tablename__ = "proyeccion_linea"

    proyeccion_linea_id: Mapped[int] = mapped_column(primary_key=True)
    proyeccion_id: Mapped[int] = mapped_column(ForeignKey("proyeccion.proyeccion_id"), nullable=False)
    edad_dias: Mapped[int]
    semana_idx: Mapped[int]
    fecha_plan: Mapped[date]
    pp_g: Mapped[float] = mapped_column(Numeric(7, 3))
    incremento_g_sem: Mapped[Optional[float]] = mapped_column(Numeric(7, 3))
    sob_pct_linea: Mapped[float] = mapped_column(Numeric(5, 2))
    cosecha_flag: Mapped[bool] = mapped_column(default=False)
    retiro_org_m2: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    nota: Mapped[Optional[str]] = mapped_column(String(255))

    proyeccion: Mapped["Proyeccion"] = relationship(back_populates="lineas")
