from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import String, Date, DateTime, Enum as SAEnum, ForeignKey, text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from enums.enums import CosechaTipoEnum, CosechaEstadoEnum


class CosechaOla(Base):
    __tablename__ = "cosecha_ola"

    cosecha_ola_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    plan_cosechas_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("plan_cosechas.plan_cosechas_id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[CosechaTipoEnum] = mapped_column(
        SAEnum(CosechaTipoEnum, native_enum=False, length=1, name="cosecha_ola_tipo_enum"),
        nullable=False,
    )
    ventana_inicio: Mapped[date]
    ventana_fin: Mapped[date]
    objetivo_retiro_org_m2: Mapped[Optional[float]] = mapped_column(DECIMAL(12, 4))
    estado: Mapped[CosechaEstadoEnum] = mapped_column(
        SAEnum(CosechaEstadoEnum, native_enum=False, length=1, name="cosecha_ola_estado_enum"),
        server_default=text("'p'"),
        nullable=False,
    )
    orden: Mapped[Optional[int]]
    notas: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True), ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )

    plan: Mapped["PlanCosechas"] = relationship(back_populates="olas")
    creador: Mapped[Optional["Usuario"]] = relationship(
        back_populates="olas_creadas",
        foreign_keys=[created_by],
    )
    cosechas: Mapped[List["CosechaEstanque"]] = relationship(
        back_populates="ola",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
