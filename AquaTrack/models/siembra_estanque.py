from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import String, Date, DateTime, Enum as SAEnum, ForeignKey, text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from enums.enums import SiembraEstadoEnum


class SiembraEstanque(Base):
    __tablename__ = "siembra_estanque"

    siembra_estanque_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    siembra_plan_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("siembra_plan.siembra_plan_id"), nullable=False)
    estanque_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("estanque.estanque_id"), nullable=False)
    estado: Mapped[SiembraEstadoEnum] = mapped_column(
        SAEnum(SiembraEstadoEnum, native_enum=False, length=1, name="siembra_estado_enum"),
        server_default=text("'p'"),
        nullable=False,
    )
    fecha_tentativa: Mapped[Optional[date]] = mapped_column(Date)
    fecha_siembra: Mapped[Optional[date]] = mapped_column(Date)
    lote: Mapped[Optional[str]] = mapped_column(String(80))
    densidad_override_org_m2: Mapped[Optional[float]] = mapped_column(DECIMAL(12, 4))
    talla_inicial_override_g: Mapped[Optional[float]] = mapped_column(DECIMAL(7, 3))
    created_by: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True), ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )
    observaciones: Mapped[Optional[str]] = mapped_column(String(150))

    siembra_plan: Mapped["SiembraPlan"] = relationship(back_populates="siembras")
    estanque: Mapped["Estanque"] = relationship(back_populates="siembras")
    creador: Mapped[Optional["Usuario"]] = relationship(
        back_populates="siembra_estanque_creadas",
        foreign_keys=[created_by],
    )
    cambios_fecha: Mapped[List["SiembraFechaLog"]] = relationship(
        back_populates="siembra_estanque",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
