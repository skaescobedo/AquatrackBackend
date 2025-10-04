from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class PlanCosechas(Base):
    __tablename__ = "plan_cosechas"

    plan_cosechas_id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo.ciclo_id"), nullable=False)
    proyeccion_id: Mapped[int] = mapped_column(ForeignKey("proyeccion.proyeccion_id"), nullable=False)
    nota_operativa: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    ciclo: Mapped["Ciclo"] = relationship(back_populates="plan_cosechas")
    proyeccion: Mapped["Proyeccion"] = relationship(back_populates="plan_cosechas")
    creador: Mapped[Optional["Usuario"]] = relationship(back_populates="planes_cosecha_creados")
    olas: Mapped[List["CosechaOla"]] = relationship(back_populates="plan", cascade="all, delete-orphan")
