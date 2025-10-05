from __future__ import annotations
from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, Date, DateTime, ForeignKey, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


class CosechaFechaLog(Base):
    __tablename__ = "cosecha_fecha_log"

    cosecha_fecha_log_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    cosecha_estanque_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("cosecha_estanque.cosecha_estanque_id"), nullable=False)
    fecha_anterior: Mapped[date]
    fecha_nueva: Mapped[date]
    motivo: Mapped[Optional[str]] = mapped_column(String(255))
    changed_by: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    cosecha_estanque: Mapped["CosechaEstanque"] = relationship(back_populates="cambios_fecha")
    autor_cambio: Mapped["Usuario"] = relationship(
        back_populates="cosecha_fecha_cambios",
        foreign_keys=[changed_by],
    )
