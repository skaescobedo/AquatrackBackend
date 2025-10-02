# models/cycle.py
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING, List

from sqlalchemy import (
    String,
    Date,
    DateTime,
    BigInteger,
    ForeignKey,
    Text,
    Numeric,
    CHAR,
    CheckConstraint,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.biometrics import Biometria, SobCambioLog
from models.harvest import PlanCosechas
from models.projection import Proyeccion
from models.seeding import SiembraPlan

if TYPE_CHECKING:
    from models.farm import Granja


# ───────────────────────────────────────────────
# Enums de Python (claridad en la app)
# ───────────────────────────────────────────────
class CicloEstado(str, Enum):
    ACTIVO = "a"
    CERRADO = "c"


# ───────────────────────────────────────────────
# Tabla: ciclo
# ───────────────────────────────────────────────
class Ciclo(Base):
    __tablename__ = "ciclo"

    ciclo_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    granja_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("granja.granja_id"), nullable=False, index=True)

    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin_planificada: Mapped[Optional[date]] = mapped_column(Date)
    fecha_cierre_real: Mapped[Optional[date]] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(CHAR(1), nullable=False, server_default="a")
    observaciones: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"),
                                                server_onupdate=text("CURRENT_TIMESTAMP"))

    # Relaciones
    granja: Mapped["Granja"] = relationship("Granja", back_populates="ciclos")

    resumen: Mapped[Optional["CicloResumen"]] = relationship(
        "CicloResumen", back_populates="ciclo", uselist=False, cascade="all, delete-orphan"
    )

    biometrias: Mapped[List["Biometria"]] = relationship(
        "Biometria", back_populates="ciclo", cascade="all, delete-orphan", lazy="selectin"
    )

    sob_cambios: Mapped[List["SobCambioLog"]] = relationship(
        "SobCambioLog", back_populates="ciclo", cascade="all, delete-orphan", lazy="selectin"
    )

    proyecciones: Mapped[List["Proyeccion"]] = relationship(
        "Proyeccion", back_populates="ciclo", cascade="all, delete-orphan", lazy="selectin"
    )

    planes_cosechas: Mapped[List["PlanCosechas"]] = relationship(
        "PlanCosechas", back_populates="ciclo", cascade="all, delete-orphan", lazy="selectin"
    )

    siembra_plan: Mapped[Optional["SiembraPlan"]] = relationship(
        "SiembraPlan", back_populates="ciclo", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("estado IN ('a','c')", name="ciclo_chk_estado"),
        Index("ix_ciclo_granja", "granja_id"),
        Index("ix_ciclo_granja_estado", "granja_id", "estado"),
        UniqueConstraint("granja_id", name="uq_ciclo_activo_por_granja",
                         sqlite_where=text("estado = 'a'")),
    )

    def __repr__(self) -> str:
        return f"<Ciclo id={self.ciclo_id} nombre={self.nombre!r} estado={self.estado!r}>"



# ───────────────────────────────────────────────
# Tabla: ciclo_resumen  (1–1 con Ciclo)
# ───────────────────────────────────────────────
class CicloResumen(Base):
    __tablename__ = "ciclo_resumen"

    ciclo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ciclo.ciclo_id"), primary_key=True
    )

    sob_final_real_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    toneladas_cosechadas: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    n_estanques_cosechados: Mapped[int] = mapped_column(nullable=False)

    fecha_inicio_real: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_fin_real: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notas_cierre: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    ciclo: Mapped["Ciclo"] = relationship("Ciclo", back_populates="resumen", lazy="joined")

    __table_args__ = (
        CheckConstraint("n_estanques_cosechados >= 0", name="cr_chk_n_estanques"),
        CheckConstraint("sob_final_real_pct >= 0 AND sob_final_real_pct <= 100", name="cr_chk_sob_final"),
        CheckConstraint("toneladas_cosechadas >= 0", name="cr_chk_toneladas"),
    )

    def __repr__(self) -> str:
        return f"<CicloResumen ciclo_id={self.ciclo_id} t={self.toneladas_cosechadas} sob={self.sob_final_real_pct}>"
