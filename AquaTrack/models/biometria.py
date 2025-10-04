from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class Biometria(Base):
    __tablename__ = "biometria"

    biometria_id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo.ciclo_id"), nullable=False)
    estanque_id: Mapped[int] = mapped_column(ForeignKey("estanque.estanque_id"), nullable=False)
    fecha: Mapped[date]
    n_muestra: Mapped[int]
    peso_muestra_g: Mapped[float] = mapped_column(Numeric(10, 3))
    pp_g: Mapped[float] = mapped_column(Numeric(7, 3))
    sob_usada_pct: Mapped[float] = mapped_column(Numeric(5, 2))
    incremento_g_sem: Mapped[Optional[float]] = mapped_column(Numeric(7, 3))
    notas: Mapped[Optional[str]] = mapped_column(String(255))
    actualiza_sob_operativa: Mapped[bool] = mapped_column(default=False)
    sob_fuente: Mapped[Optional[str]] = mapped_column(String(20))
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    ciclo: Mapped["Ciclo"] = relationship(back_populates="biometrias")
    estanque: Mapped["Estanque"] = relationship(back_populates="biometrias")
    creador: Mapped[Optional["Usuario"]] = relationship(back_populates="biometrias_creadas")
