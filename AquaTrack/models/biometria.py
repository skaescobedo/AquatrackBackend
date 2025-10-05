from __future__ import annotations
from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, Date, DateTime, Enum as SAEnum, ForeignKey, text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from enums.enums import SobFuenteEnum


class Biometria(Base):
    __tablename__ = "biometria"

    biometria_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    ciclo_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("ciclo.ciclo_id"), nullable=False)
    estanque_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("estanque.estanque_id"), nullable=False)

    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    n_muestra: Mapped[int] = mapped_column(nullable=False)
    peso_muestra_g: Mapped[float] = mapped_column(DECIMAL(10, 3), nullable=False)
    pp_g: Mapped[float] = mapped_column(DECIMAL(7, 3), nullable=False)
    sob_usada_pct: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)

    incremento_g_sem: Mapped[Optional[float]] = mapped_column(DECIMAL(7, 3))
    notas: Mapped[Optional[str]] = mapped_column(String(255))
    actualiza_sob_operativa: Mapped[bool] = mapped_column(TINYINT(1), server_default=text("0"), nullable=False)
    sob_fuente: Mapped[Optional[SobFuenteEnum]] = mapped_column(SAEnum(SobFuenteEnum, name="sob_fuente_enum", native_enum=True))
    created_by: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True), ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )

    ciclo: Mapped["Ciclo"] = relationship(back_populates="biometrias")
    estanque: Mapped["Estanque"] = relationship(back_populates="biometrias")
    creador: Mapped[Optional["Usuario"]] = relationship(
        back_populates="biometrias_creadas",
        foreign_keys=[created_by],
    )
