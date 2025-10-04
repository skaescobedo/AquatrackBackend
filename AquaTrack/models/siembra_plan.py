from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import String, Text, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class SiembraPlan(Base):
    __tablename__ = "siembra_plan"

    siembra_plan_id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo.ciclo_id"), nullable=False)
    ventana_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    ventana_fin: Mapped[date] = mapped_column(Date, nullable=False)
    densidad_org_m2: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    talla_inicial_g: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)
    observaciones: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    ciclo: Mapped["Ciclo"] = relationship(back_populates="siembra_plan")
    creador: Mapped[Optional["Usuario"]] = relationship(back_populates="siembra_estanque_creadas")
    siembras: Mapped[List["SiembraEstanque"]] = relationship(back_populates="siembra_plan", cascade="all, delete-orphan")
