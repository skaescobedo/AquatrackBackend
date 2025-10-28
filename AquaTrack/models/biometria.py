from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    BigInteger, DateTime, ForeignKey, String, Numeric, Integer,
    Boolean, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from utils.db import Base
from utils.datetime_utils import now_mazatlan


class SOBFuente(enum.Enum):
    """Origen del valor de SOB usado en la biometría"""
    operativa_actual = "operativa_actual"
    ajuste_manual = "ajuste_manual"
    reforecast = "reforecast"


class Biometria(Base):
    __tablename__ = "biometria"

    biometria_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False, index=True)
    estanque_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False, index=True)

    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    n_muestra: Mapped[int] = mapped_column(Integer, nullable=False)
    peso_muestra_g: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    pp_g: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)
    sob_usada_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    incremento_g_sem: Mapped[float | None] = mapped_column(Numeric(7, 3))
    notas: Mapped[str | None] = mapped_column(String(255))

    # Flags para actualización de SOB operativa
    actualiza_sob_operativa: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sob_fuente: Mapped[str | None] = mapped_column(SQLEnum(SOBFuente))

    # Auditoría
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now_mazatlan, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=now_mazatlan,
        onupdate=now_mazatlan,
        nullable=False
    )

    # Relationships
    ciclo: Mapped["Ciclo"] = relationship("Ciclo", foreign_keys=[ciclo_id])
    estanque: Mapped["Estanque"] = relationship("Estanque", foreign_keys=[estanque_id])
    creador: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[created_by])


class SOBCambioLog(Base):
    __tablename__ = "sob_cambio_log"

    sob_cambio_log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    estanque_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False, index=True)
    ciclo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False, index=True)

    sob_anterior_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    sob_nueva_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    fuente: Mapped[str] = mapped_column(SQLEnum(SOBFuente), nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(255))

    # Auditoría
    changed_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now_mazatlan, nullable=False)

    # Relationships
    estanque: Mapped["Estanque"] = relationship("Estanque", foreign_keys=[estanque_id])
    ciclo: Mapped["Ciclo"] = relationship("Ciclo", foreign_keys=[ciclo_id])
    modificador: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[changed_by])