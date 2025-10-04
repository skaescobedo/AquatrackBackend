from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Date, DateTime, Numeric, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class CicloResumen(Base):
    __tablename__ = "ciclo_resumen"

    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo.ciclo_id"), primary_key=True)
    sob_final_real_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    toneladas_cosechadas: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    n_estanques_cosechados: Mapped[int]
    fecha_inicio_real: Mapped[Optional[date]]
    fecha_fin_real: Mapped[Optional[date]]
    notas_cierre: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    ciclo: Mapped["Ciclo"] = relationship(back_populates="resumen")
