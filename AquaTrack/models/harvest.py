# models/harvest.py
from __future__ import annotations

from datetime import datetime, date
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    BigInteger, Date, DateTime, ForeignKey, Numeric, String,
    CheckConstraint, Index, CHAR, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.file import ArchivoPlanCosechas

if TYPE_CHECKING:
    from models.cycle import Ciclo
    from models.projection import Proyeccion
    from models.farm import Estanque
    from models.user import Usuario


# ───────────────────────────────────────────────
# Enums de Python para claridad
# ───────────────────────────────────────────────
class EstadoCosecha(str, Enum):
    PLANEADA = "p"
    REALIZADA = "r"
    CONFIRMADA = "c"
    CANCELADA = "x"


class TipoCosecha(str, Enum):
    PARCIAL = "p"
    FINAL = "f"


# ───────────────────────────────────────────────
# Tabla: plan_cosechas
# ───────────────────────────────────────────────
class PlanCosechas(Base):
    __tablename__ = "plan_cosechas"

    plan_cosechas_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False, index=True)
    proyeccion_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("proyeccion.proyeccion_id"), nullable=False, index=True)

    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    fecha_inicio_plan: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin_plan: Mapped[date] = mapped_column(Date, nullable=False)
    nota_operativa: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP")
    )

    # Relaciones
    ciclo: Mapped["Ciclo"] = relationship("Ciclo", back_populates="plan_cosechas", lazy="joined")
    proyeccion: Mapped["Proyeccion"] = relationship(
        "Proyeccion", back_populates="plan_cosechas", lazy="joined"
    )
    creador: Mapped[Optional["Usuario"]] = relationship("Usuario", lazy="joined")
    olas: Mapped[List["CosechaOla"]] = relationship(
        "CosechaOla", back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )

    archivos: Mapped[list["ArchivoPlanCosechas"]] = relationship(
        "ArchivoPlanCosechas", back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<PlanCosechas id={self.plan_cosechas_id} ciclo={self.ciclo_id}>"


# ───────────────────────────────────────────────
# Tabla: cosecha_ola
# ───────────────────────────────────────────────
class CosechaOla(Base):
    __tablename__ = "cosecha_ola"

    cosecha_ola_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plan_cosechas_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plan_cosechas.plan_cosechas_id"), nullable=False)

    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(CHAR(1), nullable=False)  # p/f
    ventana_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    ventana_fin: Mapped[date] = mapped_column(Date, nullable=False)
    objetivo_retiro_org_m2: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)

    estado: Mapped[str] = mapped_column(CHAR(1), nullable=False, default=EstadoCosecha.PLANEADA.value, server_default="p")
    orden: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP")
    )

    # Relaciones
    plan: Mapped["PlanCosechas"] = relationship("PlanCosechas", back_populates="olas", lazy="joined")
    creador: Mapped[Optional["Usuario"]] = relationship("Usuario", lazy="joined")
    cosechas: Mapped[List["CosechaEstanque"]] = relationship(
        "CosechaEstanque", back_populates="ola", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_ola_plan_estado", "plan_cosechas_id", "estado"),
        Index("ix_ola_plan_orden", "plan_cosechas_id", "orden"),
        CheckConstraint("estado in ('p','r','x')", name="ola_chk_estado"),
        CheckConstraint("objetivo_retiro_org_m2 IS NULL OR objetivo_retiro_org_m2 >= 0", name="ola_chk_objetivo"),
        CheckConstraint("tipo in ('p','f')", name="ola_chk_tipo"),
    )

    def __repr__(self) -> str:
        return f"<CosechaOla id={self.cosecha_ola_id} plan={self.plan_cosechas_id} estado={self.estado}>"


# ───────────────────────────────────────────────
# Tabla: cosecha_estanque
# ───────────────────────────────────────────────
class CosechaEstanque(Base):
    __tablename__ = "cosecha_estanque"

    cosecha_estanque_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    estanque_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False)
    cosecha_ola_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cosecha_ola.cosecha_ola_id"), nullable=False)

    tipo: Mapped[str] = mapped_column(CHAR(1), nullable=False)  # p/f
    estado: Mapped[str] = mapped_column(CHAR(1), nullable=False, default=EstadoCosecha.PLANEADA.value, server_default="p")
    fecha_cosecha: Mapped[date] = mapped_column(Date, nullable=False)

    pp_g: Mapped[Optional[float]] = mapped_column(Numeric(7, 3), nullable=True)
    biomasa_kg: Mapped[Optional[float]] = mapped_column(Numeric(14, 3), nullable=True)
    densidad_retirada_org_m2: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)

    notas: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    confirmado_por: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=True)
    confirmado_event_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP")
    )

    # Relaciones
    ola: Mapped["CosechaOla"] = relationship("CosechaOla", back_populates="cosechas", lazy="joined")
    estanque: Mapped["Estanque"] = relationship("Estanque", back_populates="cosechas", lazy="joined")
    creador: Mapped[Optional["Usuario"]] = relationship("Usuario", foreign_keys=[created_by], lazy="joined")
    confirmador: Mapped[Optional["Usuario"]] = relationship("Usuario", foreign_keys=[confirmado_por], lazy="joined")
    fecha_logs: Mapped[List["CosechaFechaLog"]] = relationship(
        "CosechaFechaLog", back_populates="cosecha_estanque", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_ce_estanque", "estanque_id"),
        Index("ix_ce_ola", "cosecha_ola_id"),
        Index("ix_ce_ola_estado", "cosecha_ola_id", "estado"),
        Index("ix_cosecha_estanque_fecha", "estanque_id", "fecha_cosecha"),
        CheckConstraint("biomasa_kg IS NULL OR biomasa_kg >= 0", name="ce_chk_biomasa"),
        CheckConstraint("densidad_retirada_org_m2 IS NULL OR densidad_retirada_org_m2 >= 0", name="ce_chk_densidad"),
        CheckConstraint("pp_g IS NULL OR pp_g >= 0", name="ce_chk_ppg"),
        CheckConstraint("estado in ('p','r','c','x')", name="ce_chk_estado"),
        CheckConstraint("tipo in ('p','f')", name="ce_chk_tipo"),
    )

    def __repr__(self) -> str:
        return f"<CosechaEstanque id={self.cosecha_estanque_id} ola={self.cosecha_ola_id} estado={self.estado}>"


# ───────────────────────────────────────────────
# Tabla: cosecha_fecha_log
# ───────────────────────────────────────────────
class CosechaFechaLog(Base):
    __tablename__ = "cosecha_fecha_log"

    cosecha_fecha_log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cosecha_estanque_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cosecha_estanque.cosecha_estanque_id"), nullable=False)

    fecha_anterior: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_nueva: Mapped[date] = mapped_column(Date, nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    changed_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Relaciones
    cosecha_estanque: Mapped["CosechaEstanque"] = relationship("CosechaEstanque", back_populates="fecha_logs", lazy="joined")
    usuario: Mapped["Usuario"] = relationship("Usuario", lazy="joined")

    def __repr__(self) -> str:
        return f"<CosechaFechaLog id={self.cosecha_fecha_log_id} cosecha_estanque_id={self.cosecha_estanque_id}>"
