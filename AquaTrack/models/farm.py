# models/farm.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    String,
    DateTime,
    BigInteger,
    Numeric,
    CheckConstraint,
    Index,
    ForeignKey,
    CHAR,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.user import Usuario, UsuarioGranja
    from models.cycle import Ciclo
    from models.biometrics import Biometria, SobCambioLog
    from models.seeding import SiembraEstanque
    from models.harvest import CosechaEstanque


# ───────────────────────────────────────────────────────────────────────────────
# Enums de Python (opcional, para claridad en la app)
# ───────────────────────────────────────────────────────────────────────────────
class EstanqueStatus(str, Enum):
    INACTIVO = "i"
    ACTIVO = "a"
    CERRADO = "c"
    MANTENIMIENTO = "m"


class SobSource(str, Enum):
    GENERAL = "general"
    MANUAL = "manual"
    REFORECAST = "reforecast"


# ───────────────────────────────────────────────────────────────────────────────
# Tabla: granja
# ───────────────────────────────────────────────────────────────────────────────
class Granja(Base):
    __tablename__ = "granja"

    granja_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    ubicacion: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # TEXT en MySQL
    superficie_total_m2: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    # Relaciones
    estanques: Mapped[List["Estanque"]] = relationship(
        "Estanque",
        back_populates="granja",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    usuarios: Mapped[List["UsuarioGranja"]] = relationship(
        "UsuarioGranja",
        back_populates="granja",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    ciclos: Mapped[List["Ciclo"]] = relationship(
        "Ciclo",
        back_populates="granja",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("superficie_total_m2 >= 0", name="granja_chk_superficie"),
    )

    def __repr__(self) -> str:
        return f"<Granja id={self.granja_id} nombre={self.nombre!r}>"


# ───────────────────────────────────────────────────────────────────────────────
# Tabla: estanque
# ───────────────────────────────────────────────────────────────────────────────
class Estanque(Base):
    __tablename__ = "estanque"

    estanque_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    granja_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("granja.granja_id"),
        nullable=False,
        index=True,
    )

    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    superficie_m2: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    status: Mapped[str] = mapped_column(
        CHAR(1),
        nullable=False,
        default=EstanqueStatus.INACTIVO.value,
        server_default="i",
    )
    sob_estanque_pct: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=100.00, server_default="100.00"
    )

    sob_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sob_updated_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("usuario.usuario_id"), nullable=True
    )
    # En BD es ENUM('general','manual','reforecast'); aquí lo dejamos como String para mantener portabilidad.
    # Si quieres reflejar el Enum de Python, podrías usar SAEnum(SobSource), pero no es obligatorio.
    sob_source: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    sob_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    # Relaciones
    granja: Mapped["Granja"] = relationship(
        "Granja", back_populates="estanques", lazy="joined"
    )

    sob_user: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        primaryjoin="Estanque.sob_updated_by == Usuario.usuario_id",
        lazy="joined",
    )

    # Biometrías y cambios de SOB
    biometrias: Mapped[List["Biometria"]] = relationship(
        "Biometria", back_populates="estanque", cascade="all, delete-orphan", lazy="selectin"
    )
    sob_cambios: Mapped[List["SobCambioLog"]] = relationship(
        "SobCambioLog", back_populates="estanque", cascade="all, delete-orphan", lazy="selectin"
    )

    # Siembras y Cosechas (faltantes)
    siembras: Mapped[List["SiembraEstanque"]] = relationship(
        "SiembraEstanque", back_populates="estanque", cascade="all, delete-orphan", lazy="selectin"
    )
    cosechas: Mapped[List["CosechaEstanque"]] = relationship(
        "CosechaEstanque", back_populates="estanque", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_estanque_granja", "granja_id"),
        Index("ix_estanque_status", "status"),
        CheckConstraint("superficie_m2 > 0", name="estanque_chk_superficie"),
        CheckConstraint(
            "sob_estanque_pct >= 0 AND sob_estanque_pct <= 100", name="estanque_chk_sob"
        ),
        CheckConstraint("status in ('i','a','c','m')", name="estanque_chk_status"),
        # Si quieres validar también sob_source en la app:
        # CheckConstraint("sob_source in ('general','manual','reforecast')", name="estanque_chk_sob_source"),
    )

    def __repr__(self) -> str:
        return f"<Estanque id={self.estanque_id} granja_id={self.granja_id} nombre={self.nombre!r} status={self.status!r}>"
