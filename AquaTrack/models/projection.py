# models/projection.py
from __future__ import annotations

from datetime import datetime, date
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    String, DateTime, BigInteger, Integer, Numeric, Boolean, ForeignKey,
    CheckConstraint, Index, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.file import ArchivoProyeccion
from models.harvest import PlanCosechas

if TYPE_CHECKING:
    from models.user import Usuario
    from models.cycle import Ciclo


# ──────────────────────────────────────────────
# Enums de Python (para el código, no la BD)
# ──────────────────────────────────────────────
class ProyeccionStatus(str, Enum):
    BORRADOR = "b"
    PUBLICADA = "p"
    REFORECAST = "r"
    CANCELADA = "x"


class ProyeccionSource(str, Enum):
    AUTO = "auto"
    ARCHIVO = "archivo"
    REFORECAST = "reforecast"


# ──────────────────────────────────────────────
# Tabla: proyeccion
# ──────────────────────────────────────────────
class Proyeccion(Base):
    __tablename__ = "proyeccion"

    proyeccion_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False, index=True)

    version: Mapped[str] = mapped_column(String(20), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(1), nullable=False, default=ProyeccionStatus.BORRADOR.value, server_default="b")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    creada_por: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=True)

    source_type: Mapped[Optional[str]] = mapped_column(String(10))
    source_ref: Mapped[Optional[str]] = mapped_column(String(120))
    parent_version_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("proyeccion.proyeccion_id"))

    siembra_ventana_inicio: Mapped[Optional[date]] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP")
    )

    # Relaciones
    ciclo: Mapped["Ciclo"] = relationship("Ciclo", back_populates="proyecciones", lazy="joined")
    creador: Mapped[Optional["Usuario"]] = relationship("Usuario", lazy="joined")
    parent: Mapped[Optional["Proyeccion"]] = relationship("Proyeccion", remote_side=[proyeccion_id], lazy="joined")

    lineas: Mapped[List["ProyeccionLinea"]] = relationship(
        "ProyeccionLinea", back_populates="proyeccion", cascade="all, delete-orphan", lazy="selectin"
    )

    parametros: Mapped[Optional["ParametroCicloVersion"]] = relationship(
        "ParametroCicloVersion", back_populates="proyeccion", uselist=False, lazy="joined"
    )

    # (Opcional pero útil) Plan de Cosechas (1:1 desde proyección)
    plan_cosechas: Mapped[Optional["PlanCosechas"]] = relationship(
        "PlanCosechas", back_populates="proyeccion", uselist=False, lazy="selectin"
    )

    archivos: Mapped[list["ArchivoProyeccion"]] = relationship(
        "ArchivoProyeccion", back_populates="proyeccion", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_proy_ciclo", "ciclo_id"),
        CheckConstraint("status in ('b','p','r','x')", name="proyeccion_chk_status"),
    )

    def __repr__(self) -> str:
        return f"<Proyeccion id={self.proyeccion_id} ciclo_id={self.ciclo_id} version={self.version!r} status={self.status!r}>"


# ──────────────────────────────────────────────
# Tabla: proyeccion_linea
# ──────────────────────────────────────────────
class ProyeccionLinea(Base):
    __tablename__ = "proyeccion_linea"

    proyeccion_linea_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    proyeccion_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("proyeccion.proyeccion_id"), nullable=False, index=True)

    edad_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    semana_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_plan: Mapped[date] = mapped_column(nullable=False)

    pp_g: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)
    incremento_g_sem: Mapped[Optional[float]] = mapped_column(Numeric(7, 3))
    sob_pct_linea: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    cosecha_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))
    retiro_org_m2: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    nota: Mapped[Optional[str]] = mapped_column(String(255))

    # Relaciones
    proyeccion: Mapped["Proyeccion"] = relationship("Proyeccion", back_populates="lineas", lazy="joined")

    __table_args__ = (
        Index("ix_pl_proy", "proyeccion_id"),
        Index("ix_pl_proy_semana", "proyeccion_id", "semana_idx"),
        CheckConstraint("edad_dias >= 0", name="pl_chk_edad"),
        CheckConstraint("pp_g >= 0", name="pl_chk_ppg"),
        CheckConstraint("semana_idx >= 0", name="pl_chk_semana"),
        CheckConstraint("sob_pct_linea >= 0 AND sob_pct_linea <= 100", name="pl_chk_sob"),
        CheckConstraint("retiro_org_m2 IS NULL OR retiro_org_m2 >= 0", name="pl_chk_retiro"),
    )

    def __repr__(self) -> str:
        return f"<ProyeccionLinea id={self.proyeccion_linea_id} semana={self.semana_idx} pp_g={self.pp_g}>"


# ──────────────────────────────────────────────
# Tabla: parametro_ciclo_version
# ──────────────────────────────────────────────
class ParametroCicloVersion(Base):
    __tablename__ = "parametro_ciclo_version"

    parametro_ciclo_version_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False, index=True)
    proyeccion_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("proyeccion.proyeccion_id"), nullable=False, unique=True)

    sob_actual_pct_snapshot: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    sob_final_objetivo_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    nota: Mapped[Optional[str]] = mapped_column(String(255))
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"))

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP")
    )

    # Relaciones
    proyeccion: Mapped["Proyeccion"] = relationship("Proyeccion", back_populates="parametros", lazy="joined")
    ciclo: Mapped["Ciclo"] = relationship("Ciclo", back_populates="parametros", lazy="joined")
    usuario: Mapped[Optional["Usuario"]] = relationship("Usuario", lazy="joined")

    __table_args__ = (
        CheckConstraint("sob_actual_pct_snapshot >= 0 AND sob_actual_pct_snapshot <= 100", name="pcv_chk_sob_actual"),
        CheckConstraint("sob_final_objetivo_pct >= 0 AND sob_final_objetivo_pct <= 100", name="pcv_chk_sob_final"),
    )

    def __repr__(self) -> str:
        return f"<ParametroCicloVersion id={self.parametro_ciclo_version_id} ciclo_id={self.ciclo_id} proyeccion_id={self.proyeccion_id}>"
