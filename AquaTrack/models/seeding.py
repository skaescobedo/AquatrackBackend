# models/seeding.py
from __future__ import annotations

from datetime import datetime, date
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    BigInteger, Date, DateTime, ForeignKey, Numeric, String, Text,
    CheckConstraint, Index, CHAR, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.file import ArchivoSiembraPlan

if TYPE_CHECKING:
    from models.cycle import Ciclo
    from models.farm import Estanque
    from models.user import Usuario


# ───────────────────────────────────────────────
# Enums de Python (opcional)
# ───────────────────────────────────────────────
class EstadoSiembra(str, Enum):
    PLANEADA = "p"
    FINALIZADA = "f"


# ───────────────────────────────────────────────
# Tabla: siembra_plan
# ───────────────────────────────────────────────
class SiembraPlan(Base):
    __tablename__ = "siembra_plan"

    siembra_plan_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False, index=True)

    ventana_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    ventana_fin: Mapped[date] = mapped_column(Date, nullable=False)

    densidad_org_m2: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    talla_inicial_g: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)

    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP")
    )

    # Relaciones
    ciclo: Mapped["Ciclo"] = relationship("Ciclo", back_populates="siembra_plan", lazy="joined")
    creador: Mapped[Optional["Usuario"]] = relationship("Usuario", lazy="joined")
    estanques: Mapped[List["SiembraEstanque"]] = relationship(
        "SiembraEstanque", back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )

    archivos: Mapped[list["ArchivoSiembraPlan"]] = relationship(
        "ArchivoSiembraPlan", back_populates="siembra_plan", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("densidad_org_m2 >= 0", name="sp_chk_densidad"),
        CheckConstraint("talla_inicial_g >= 0", name="sp_chk_talla"),
    )

    def __repr__(self) -> str:
        return f"<SiembraPlan id={self.siembra_plan_id} ciclo_id={self.ciclo_id}>"


# ───────────────────────────────────────────────
# Tabla: siembra_estanque
# ───────────────────────────────────────────────
class SiembraEstanque(Base):
    __tablename__ = "siembra_estanque"

    siembra_estanque_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    siembra_plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("siembra_plan.siembra_plan_id"), nullable=False)
    estanque_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False)

    estado: Mapped[str] = mapped_column(CHAR(1), nullable=False, default=EstadoSiembra.PLANEADA.value, server_default="p")
    fecha_tentativa: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_siembra: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    lote: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    densidad_override_org_m2: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    talla_inicial_override_g: Mapped[Optional[float]] = mapped_column(Numeric(7, 3), nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP")
    )

    # Relaciones
    plan: Mapped["SiembraPlan"] = relationship("SiembraPlan", back_populates="estanques", lazy="joined")
    estanque: Mapped["Estanque"] = relationship("Estanque", back_populates="siembras", lazy="joined")
    creador: Mapped[Optional["Usuario"]] = relationship("Usuario", lazy="joined")
    fecha_logs: Mapped[List["SiembraFechaLog"]] = relationship(
        "SiembraFechaLog", back_populates="siembra_estanque", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_se_plan", "siembra_plan_id"),
        Index("ix_se_estanque", "estanque_id"),
        Index("ix_se_plan_estado", "siembra_plan_id", "estado"),
        CheckConstraint("densidad_override_org_m2 IS NULL OR densidad_override_org_m2 >= 0", name="se_chk_densidad"),
        CheckConstraint("talla_inicial_override_g IS NULL OR talla_inicial_override_g >= 0", name="se_chk_talla"),
        CheckConstraint("estado in ('p','f')", name="se_chk_estado"),
    )

    def __repr__(self) -> str:
        return f"<SiembraEstanque id={self.siembra_estanque_id} plan_id={self.siembra_plan_id} estado={self.estado}>"


# ───────────────────────────────────────────────
# Tabla: siembra_fecha_log
# ───────────────────────────────────────────────
class SiembraFechaLog(Base):
    __tablename__ = "siembra_fecha_log"

    siembra_fecha_log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    siembra_estanque_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("siembra_estanque.siembra_estanque_id"), nullable=False)

    fecha_anterior: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_nueva: Mapped[date] = mapped_column(Date, nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    changed_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Relaciones
    siembra_estanque: Mapped["SiembraEstanque"] = relationship("SiembraEstanque", back_populates="fecha_logs", lazy="joined")
    usuario: Mapped["Usuario"] = relationship("Usuario", lazy="joined")

    def __repr__(self) -> str:
        return f"<SiembraFechaLog id={self.siembra_fecha_log_id} se_id={self.siembra_estanque_id}>"
