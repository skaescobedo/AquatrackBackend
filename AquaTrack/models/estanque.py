from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from enums.enums import EstanqueStatusEnum


class Estanque(Base):
    __tablename__ = "estanque"

    estanque_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    granja_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("granja.granja_id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    superficie_m2: Mapped[float] = mapped_column(DECIMAL(14, 2), nullable=False)
    status: Mapped[EstanqueStatusEnum] = mapped_column(
        SAEnum(EstanqueStatusEnum, native_enum=False, length=1, name="estanque_status_enum"),
        server_default=text("'i'"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )

    granja: Mapped["Granja"] = relationship(back_populates="estanques")

    siembras: Mapped[List["SiembraEstanque"]] = relationship(back_populates="estanque", lazy="selectin")
    cosechas: Mapped[List["CosechaEstanque"]] = relationship(back_populates="estanque", lazy="selectin")
    biometrias: Mapped[List["Biometria"]] = relationship(back_populates="estanque", lazy="selectin")
    sob_logs: Mapped[List["SobCambioLog"]] = relationship(back_populates="estanque", lazy="selectin")
