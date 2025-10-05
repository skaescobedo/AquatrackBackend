from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from enums.enums import SobFuenteEnum


class SobCambioLog(Base):
    __tablename__ = "sob_cambio_log"

    sob_cambio_log_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    estanque_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("estanque.estanque_id"), nullable=False)
    ciclo_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("ciclo.ciclo_id"), nullable=False)
    sob_anterior_pct: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    sob_nueva_pct: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    fuente: Mapped[SobFuenteEnum] = mapped_column(SAEnum(SobFuenteEnum, name="sob_fuente_enum", native_enum=True), nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String(255))
    changed_by: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    estanque: Mapped["Estanque"] = relationship(back_populates="sob_logs")
    ciclo: Mapped["Ciclo"] = relationship(back_populates="sob_logs")
    autor_cambio: Mapped["Usuario"] = relationship(
        back_populates="sob_cambios",
        foreign_keys=[changed_by],
    )
