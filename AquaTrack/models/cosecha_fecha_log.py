from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class CosechaFechaLog(Base):
    __tablename__ = "cosecha_fecha_log"

    cosecha_fecha_log_id: Mapped[int] = mapped_column(primary_key=True)
    cosecha_estanque_id: Mapped[int] = mapped_column(ForeignKey("cosecha_estanque.cosecha_estanque_id"), nullable=False)
    fecha_anterior: Mapped[date]
    fecha_nueva: Mapped[date]
    motivo: Mapped[Optional[str]] = mapped_column(String(255))
    changed_by: Mapped[int] = mapped_column(ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    cosecha_estanque: Mapped["CosechaEstanque"] = relationship(back_populates="cambios_fecha")
    autor_cambio: Mapped["Usuario"] = relationship(back_populates="cosecha_fecha_cambios")
