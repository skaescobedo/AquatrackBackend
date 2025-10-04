from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Numeric, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class SobCambioLog(Base):
    __tablename__ = "sob_cambio_log"

    sob_cambio_log_id: Mapped[int] = mapped_column(primary_key=True)
    estanque_id: Mapped[int] = mapped_column(ForeignKey("estanque.estanque_id"), nullable=False)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo.ciclo_id"), nullable=False)
    sob_anterior_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    sob_nueva_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    fuente: Mapped[str] = mapped_column(Enum("operativa_actual", "ajuste_manual", "reforecast", name="sob_fuente_enum"), nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String(255))
    changed_by: Mapped[int] = mapped_column(ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    estanque: Mapped["Estanque"] = relationship(back_populates="sob_logs")
    ciclo: Mapped["Ciclo"] = relationship(back_populates="sob_logs")
    autor_cambio: Mapped["Usuario"] = relationship(back_populates="sob_cambios")
