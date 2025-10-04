from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, Date, DateTime, Numeric, CHAR, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class CosechaOla(Base):
    __tablename__ = "cosecha_ola"

    cosecha_ola_id: Mapped[int] = mapped_column(primary_key=True)
    plan_cosechas_id: Mapped[int] = mapped_column(ForeignKey("plan_cosechas.plan_cosechas_id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(CHAR(1), nullable=False)  # p/f
    ventana_inicio: Mapped[date]
    ventana_fin: Mapped[date]
    objetivo_retiro_org_m2: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    estado: Mapped[str] = mapped_column(CHAR(1), default="p", nullable=False)  # p/r/x
    orden: Mapped[Optional[int]]
    notas: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    plan: Mapped["PlanCosechas"] = relationship(back_populates="olas")
    creador: Mapped[Optional["Usuario"]] = relationship(back_populates="olas_creadas")
    cosechas: Mapped[List["CosechaEstanque"]] = relationship(back_populates="ola", cascade="all, delete-orphan")
