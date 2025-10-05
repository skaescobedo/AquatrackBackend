from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import String, Date, DateTime, Enum as SAEnum, ForeignKey, text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from enums.enums import CosechaEstadoDetEnum


class CosechaEstanque(Base):
    __tablename__ = "cosecha_estanque"

    cosecha_estanque_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    estanque_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("estanque.estanque_id"), nullable=False)
    cosecha_ola_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("cosecha_ola.cosecha_ola_id"), nullable=False)
    estado: Mapped[CosechaEstadoDetEnum] = mapped_column(
        SAEnum(CosechaEstadoDetEnum, native_enum=False, length=1, name="cosecha_est_det_estado_enum"),
        server_default=text("'p'"),
        nullable=False,
    )
    fecha_cosecha: Mapped[date] = mapped_column(Date, nullable=False)

    pp_g: Mapped[Optional[float]] = mapped_column(DECIMAL(7, 3))
    biomasa_kg: Mapped[Optional[float]] = mapped_column(DECIMAL(14, 3))
    densidad_retirada_org_m2: Mapped[Optional[float]] = mapped_column(DECIMAL(12, 4))
    notas: Mapped[Optional[str]] = mapped_column(String(255))
    confirmado_por: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True), ForeignKey("usuario.usuario_id"))
    confirmado_event_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_by: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True), ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )

    estanque: Mapped["Estanque"] = relationship(back_populates="cosechas")
    ola: Mapped["CosechaOla"] = relationship(back_populates="cosechas")

    confirmador: Mapped[Optional["Usuario"]] = relationship(
        back_populates="cosechas_confirmadas",
        foreign_keys=[confirmado_por],
    )
    creador: Mapped[Optional["Usuario"]] = relationship(
        back_populates="cosechas_creadas",
        foreign_keys=[created_by],
    )

    cambios_fecha: Mapped[List["CosechaFechaLog"]] = relationship(
        back_populates="cosecha_estanque",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
