from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import String, Text, Date, DateTime, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


class SiembraPlan(Base):
    __tablename__ = "siembra_plan"
    __table_args__ = (
        UniqueConstraint("ciclo_id", name="uq_sp_por_ciclo"),
        Index("ix_sp_ciclo", "ciclo_id"),  # refleja el índice que ya existe en BD
    )

    siembra_plan_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    ciclo_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("ciclo.ciclo_id"), nullable=False)
    ventana_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    ventana_fin: Mapped[date] = mapped_column(Date, nullable=False)
    densidad_org_m2: Mapped[float] = mapped_column(DECIMAL(12, 4), nullable=False)
    talla_inicial_g: Mapped[float] = mapped_column(DECIMAL(7, 3), nullable=False)
    observaciones: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True), ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )

    ciclo: Mapped["Ciclo"] = relationship(back_populates="siembra_plan")
    creador: Mapped[Optional["Usuario"]] = relationship(
        back_populates="planes_siembra_creados",
        foreign_keys=[created_by],
    )
    siembras: Mapped[List["SiembraEstanque"]] = relationship(
        back_populates="siembra_plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
