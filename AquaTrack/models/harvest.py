# models/harvest.py
from __future__ import annotations

from datetime import datetime, date
from sqlalchemy import (
    BigInteger, Date, DateTime, ForeignKey, String, Text, Numeric, CHAR, Integer
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from utils.datetime_utils import now_mazatlan


class CosechaOla(Base):
    __tablename__ = "cosecha_ola"

    cosecha_ola_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False, index=True)

    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(CHAR(1), nullable=False)  # 'p' parcial, 'f' final
    ventana_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    ventana_fin: Mapped[date] = mapped_column(Date, nullable=False)

    objetivo_retiro_org_m2: Mapped[float | None] = mapped_column(Numeric(12, 4))
    status: Mapped[str] = mapped_column(CHAR(1), default="p", nullable=False)  # 'p' pendiente, 'r' en ruta, 'x' cancelada
    orden: Mapped[int | None] = mapped_column(Integer)
    notas: Mapped[str | None] = mapped_column(String(255))

    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now_mazatlan, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now_mazatlan, onupdate=now_mazatlan, nullable=False)

    # Relationships
    cosechas: Mapped[list["CosechaEstanque"]] = relationship(
        "CosechaEstanque", back_populates="ola", cascade="all, delete-orphan"
    )


class CosechaEstanque(Base):
    __tablename__ = "cosecha_estanque"

    cosecha_estanque_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    estanque_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False, index=True)
    cosecha_ola_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cosecha_ola.cosecha_ola_id"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(CHAR(1), default="p", nullable=False)  # 'p' pendiente, 'c' confirmada, 'x' cancelada
    fecha_cosecha: Mapped[date] = mapped_column(Date, nullable=False)

    pp_g: Mapped[float | None] = mapped_column(Numeric(7, 3))
    biomasa_kg: Mapped[float | None] = mapped_column(Numeric(14, 3))
    densidad_retirada_org_m2: Mapped[float | None] = mapped_column(Numeric(12, 4))
    notas: Mapped[str | None] = mapped_column(String(255))

    confirmado_por: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"))
    confirmado_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now_mazatlan, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now_mazatlan, onupdate=now_mazatlan, nullable=False)

    # Relationships
    ola: Mapped["CosechaOla"] = relationship("CosechaOla", back_populates="cosechas")


class CosechaFechaLog(Base):
    __tablename__ = "cosecha_fecha_log"

    cosecha_fecha_log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cosecha_estanque_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cosecha_estanque.cosecha_estanque_id", ondelete="CASCADE"), nullable=False)

    fecha_anterior: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_nueva: Mapped[date] = mapped_column(Date, nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(255))

    changed_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now_mazatlan, nullable=False)
