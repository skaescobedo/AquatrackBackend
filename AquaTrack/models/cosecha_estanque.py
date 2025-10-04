from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Date, DateTime, Numeric, CHAR, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class CosechaEstanque(Base):
    __tablename__ = "cosecha_estanque"

    cosecha_estanque_id: Mapped[int] = mapped_column(primary_key=True)
    estanque_id: Mapped[int] = mapped_column(ForeignKey("estanque.estanque_id"), nullable=False)
    cosecha_ola_id: Mapped[int] = mapped_column(ForeignKey("cosecha_ola.cosecha_ola_id"), nullable=False)
    estado: Mapped[str] = mapped_column(CHAR(1), default="p", nullable=False)  # p/c/x
    fecha_cosecha: Mapped[date]
    pp_g: Mapped[Optional[float]] = mapped_column(Numeric(7, 3))
    biomasa_kg: Mapped[Optional[float]] = mapped_column(Numeric(14, 3))
    densidad_retirada_org_m2: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    notas: Mapped[Optional[str]] = mapped_column(String(255))
    confirmado_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.usuario_id"))
    confirmado_event_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    estanque: Mapped["Estanque"] = relationship(back_populates="cosechas")
    ola: Mapped["CosechaOla"] = relationship(back_populates="cosechas")
    confirmador: Mapped[Optional["Usuario"]] = relationship(back_populates="cosechas_confirmadas", foreign_keys=[confirmado_por])
    creador: Mapped[Optional["Usuario"]] = relationship(back_populates="cosechas_creadas", foreign_keys=[created_by])
    cambios_fecha: Mapped[list["CosechaFechaLog"]] = relationship(back_populates="cosecha_estanque", cascade="all, delete-orphan")
