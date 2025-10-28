from __future__ import annotations

from datetime import datetime, date
from sqlalchemy import (
    BigInteger, Date, DateTime, ForeignKey, String, Text, Numeric, CHAR, func, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base

class SiembraPlan(Base):
    __tablename__ = "siembra_plan"
    __table_args__ = (
        UniqueConstraint("ciclo_id", name="uq_siembra_plan_ciclo"),
    )

    siembra_plan_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False, index=True)

    ventana_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    ventana_fin: Mapped[date] = mapped_column(Date, nullable=False)

    densidad_org_m2: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    talla_inicial_g: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)

    status: Mapped[str] = mapped_column(CHAR(1), default="p", nullable=False)  # p=e=f
    observaciones: Mapped[str | None] = mapped_column(Text())

    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    ciclo: Mapped["Ciclo"] = relationship("Ciclo", back_populates="siembra_plan")
    siembras: Mapped[list["SiembraEstanque"]] = relationship(
        "SiembraEstanque", back_populates="plan", cascade="all, delete-orphan"
    )


class SiembraEstanque(Base):
    __tablename__ = "siembra_estanque"

    siembra_estanque_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    siembra_plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("siembra_plan.siembra_plan_id"), nullable=False, index=True)
    estanque_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(CHAR(1), default="p", nullable=False)  # p=pendiente, f=finalizada
    fecha_tentativa: Mapped[date | None] = mapped_column(Date)
    fecha_siembra: Mapped[date | None] = mapped_column(Date)

    lote: Mapped[str | None] = mapped_column(String(80))
    densidad_override_org_m2: Mapped[float | None] = mapped_column(Numeric(12, 4))
    talla_inicial_override_g: Mapped[float | None] = mapped_column(Numeric(7, 3))

    observaciones: Mapped[str | None] = mapped_column(String(150))

    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    plan: Mapped["SiembraPlan"] = relationship("SiembraPlan", back_populates="siembras")
    estanque: Mapped["Estanque"] = relationship("Estanque")
    fecha_logs: Mapped[list["SiembraFechaLog"]] = relationship(
        "SiembraFechaLog", back_populates="siembra", cascade="all, delete-orphan"
    )


class SiembraFechaLog(Base):
    __tablename__ = "siembra_fecha_log"

    siembra_fecha_log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    siembra_estanque_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("siembra_estanque.siembra_estanque_id", ondelete="CASCADE"), nullable=False)

    fecha_anterior: Mapped[date | None] = mapped_column(Date)
    fecha_nueva: Mapped[date] = mapped_column(Date, nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(255))

    changed_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    siembra: Mapped["SiembraEstanque"] = relationship("SiembraEstanque", back_populates="fecha_logs")
