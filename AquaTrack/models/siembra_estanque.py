from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Date, DateTime, Numeric, CHAR, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class  SiembraEstanque(Base):
    __tablename__ = "siembra_estanque"

    siembra_estanque_id: Mapped[int] = mapped_column(primary_key=True)
    siembra_plan_id: Mapped[int] = mapped_column(ForeignKey("siembra_plan.siembra_plan_id"), nullable=False)
    estanque_id: Mapped[int] = mapped_column(ForeignKey("estanque.estanque_id"), nullable=False)
    estado: Mapped[str] = mapped_column(CHAR(1), default="p", nullable=False)  # p/f
    fecha_tentativa: Mapped[Optional[date]] = mapped_column(Date)
    fecha_siembra: Mapped[Optional[date]] = mapped_column(Date)
    lote: Mapped[Optional[str]] = mapped_column(String(80))
    densidad_override_org_m2: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    talla_inicial_override_g: Mapped[Optional[float]] = mapped_column(Numeric(7, 3))
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    siembra_plan: Mapped["SiembraPlan"] = relationship(back_populates="siembras")
    estanque: Mapped["Estanque"] = relationship(back_populates="siembras")
    creador: Mapped[Optional["Usuario"]] = relationship(back_populates="siembra_estanque_creadas")
    cambios_fecha: Mapped[list["SiembraFechaLog"]] = relationship(back_populates="siembra_estanque", cascade="all, delete-orphan")
