from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, DateTime, Numeric, ForeignKey, CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class Estanque(Base):
    __tablename__ = "estanque"

    estanque_id: Mapped[int] = mapped_column(primary_key=True)
    granja_id: Mapped[int] = mapped_column(ForeignKey("granja.granja_id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    superficie_m2: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(CHAR(1), default="i", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    granja: Mapped["Granja"] = relationship(back_populates="estanques")

    siembras: Mapped[List["SiembraEstanque"]] = relationship(back_populates="estanque")
    cosechas: Mapped[List["CosechaEstanque"]] = relationship(back_populates="estanque")
    biometrias: Mapped[List["Biometria"]] = relationship(back_populates="estanque")
    sob_logs: Mapped[List["SobCambioLog"]] = relationship(back_populates="estanque")
