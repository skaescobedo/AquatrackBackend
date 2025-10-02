# models/file.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    BigInteger, DateTime, ForeignKey, String,
    CheckConstraint, Index, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.user import Usuario
    from models.projection import Proyeccion
    from models.harvest import PlanCosechas
    from models.seeding import SiembraPlan


# ───────────────────────────────────────────────
# Enums (solo para claridad en Python)
# ───────────────────────────────────────────────
class PropositoPlanCosechas(str, Enum):
    PLANTILLA = "plantilla"
    RESPALDO = "respaldo"
    OTRO = "otro"


class PropositoSiembraPlan(str, Enum):
    PLANTILLA = "plantilla"
    RESPALDO = "respaldo"
    OTRO = "otro"


class PropositoProyeccion(str, Enum):
    INSUMO_CALCULO = "insumo_calculo"
    RESPALDO = "respaldo"
    REPORTE_PUBLICADO = "reporte_publicado"
    OTRO = "otro"


# ───────────────────────────────────────────────
# Tabla: archivo
# ───────────────────────────────────────────────
class Archivo(Base):
    __tablename__ = "archivo"

    archivo_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nombre_original: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo_mime: Mapped[str] = mapped_column(String(120), nullable=False)
    tamanio_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(300), nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    subido_por: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("usuario.usuario_id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    # Relaciones
    usuario: Mapped[Optional["Usuario"]] = relationship(
        "Usuario", back_populates="archivos_subidos", lazy="joined"
    )

    # Backrefs a vínculos
    enlaces_proyeccion: Mapped[List["ArchivoProyeccion"]] = relationship(
        "ArchivoProyeccion", back_populates="archivo", cascade="all, delete-orphan", lazy="selectin"
    )
    enlaces_plan_cosechas: Mapped[List["ArchivoPlanCosechas"]] = relationship(
        "ArchivoPlanCosechas", back_populates="archivo", cascade="all, delete-orphan", lazy="selectin"
    )
    enlaces_siembra_plan: Mapped[List["ArchivoSiembraPlan"]] = relationship(
        "ArchivoSiembraPlan", back_populates="archivo", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("tamanio_bytes >= 0", name="archivo_chk_tamanio_nonneg"),
        # Tip: podrías añadir UNIQUE(storage_path) si cada path debe ser único.
    )

    def __repr__(self) -> str:
        return f"<Archivo id={self.archivo_id} nombre={self.nombre_original!r}>"


# ───────────────────────────────────────────────
# Tabla: archivo_proyeccion
# ───────────────────────────────────────────────
class ArchivoProyeccion(Base):
    __tablename__ = "archivo_proyeccion"

    archivo_proyeccion_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    archivo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("archivo.archivo_id"), nullable=False, index=True)
    proyeccion_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("proyeccion.proyeccion_id"), nullable=False, index=True)

    # Longest value is 'reporte_publicado' (17), String(20) deja margen
    proposito: Mapped[str] = mapped_column(String(20), nullable=False, server_default="otro")
    notas: Mapped[Optional[str]] = mapped_column(String(255))

    linked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Relaciones
    archivo: Mapped["Archivo"] = relationship("Archivo", back_populates="enlaces_proyeccion", lazy="joined")
    proyeccion: Mapped["Proyeccion"] = relationship("Proyeccion", back_populates="archivos", lazy="joined")

    __table_args__ = (
        Index("ix_ap_archivo", "archivo_id"),
        Index("ix_ap_proy", "proyeccion_id"),
        CheckConstraint(
            "proposito in ('insumo_calculo','respaldo','reporte_publicado','otro')",
            name="ap_chk_proposito"
        ),
    )

    def __repr__(self) -> str:
        return f"<ArchivoProyeccion id={self.archivo_proyeccion_id} proy={self.proyeccion_id}>"


# ───────────────────────────────────────────────
# Tabla: archivo_plan_cosechas
# ───────────────────────────────────────────────
class ArchivoPlanCosechas(Base):
    __tablename__ = "archivo_plan_cosechas"

    archivo_plan_cosechas_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    archivo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("archivo.archivo_id"), nullable=False, index=True)
    plan_cosechas_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plan_cosechas.plan_cosechas_id"), nullable=False, index=True)

    proposito: Mapped[str] = mapped_column(String(20), nullable=False, server_default="plantilla")
    notas: Mapped[Optional[str]] = mapped_column(String(255))

    linked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Relaciones
    archivo: Mapped["Archivo"] = relationship("Archivo", back_populates="enlaces_plan_cosechas", lazy="joined")
    plan: Mapped["PlanCosechas"] = relationship("PlanCosechas", back_populates="archivos", lazy="joined")

    __table_args__ = (
        Index("ix_apc_archivo", "archivo_id"),
        Index("ix_apc_plan", "plan_cosechas_id"),
        CheckConstraint(
            "proposito in ('plantilla','respaldo','otro')",
            name="apc_chk_proposito"
        ),
    )

    def __repr__(self) -> str:
        return f"<ArchivoPlanCosechas id={self.archivo_plan_cosechas_id} plan={self.plan_cosechas_id}>"


# ───────────────────────────────────────────────
# Tabla: archivo_siembra_plan
# ───────────────────────────────────────────────
class ArchivoSiembraPlan(Base):
    __tablename__ = "archivo_siembra_plan"

    archivo_siembra_plan_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    archivo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("archivo.archivo_id"), nullable=False, index=True)
    siembra_plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("siembra_plan.siembra_plan_id"), nullable=False, index=True)

    proposito: Mapped[str] = mapped_column(String(20), nullable=False, server_default="plantilla")
    notas: Mapped[Optional[str]] = mapped_column(String(255))

    linked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Relaciones
    archivo: Mapped["Archivo"] = relationship("Archivo", back_populates="enlaces_siembra_plan", lazy="joined")
    siembra_plan: Mapped["SiembraPlan"] = relationship("SiembraPlan", back_populates="archivos", lazy="joined")

    __table_args__ = (
        Index("ix_asp_archivo", "archivo_id"),
        Index("ix_asp_plan", "siembra_plan_id"),
        CheckConstraint(
            "proposito in ('plantilla','respaldo','otro')",
            name="asp_chk_proposito"
        ),
    )

    def __repr__(self) -> str:
        return f"<ArchivoSiembraPlan id={self.archivo_siembra_plan_id} sp={self.siembra_plan_id}>"
