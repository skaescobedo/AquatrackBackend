from __future__ import annotations

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    String, DateTime, BigInteger, ForeignKey, Table,
    UniqueConstraint, CheckConstraint, Index, CHAR
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.file import Archivo

if TYPE_CHECKING:
    from models.farm import Granja
    from models.biometrics import Biometria, SobCambioLog
    from models.projection import Proyeccion, ParametroCicloVersion
    from models.seeding import SiembraPlan, SiembraEstanque, SiembraFechaLog
    from models.harvest import PlanCosechas, CosechaOla, CosechaEstanque, CosechaFechaLog
    from models.task import Tarea


# ────────────────────────────────────────────────────────────────────────────────
# Association Table: usuario_rol  (many-to-many simple, sin campos extra)
# ────────────────────────────────────────────────────────────────────────────────
usuario_rol = Table(
    "usuario_rol",
    Base.metadata,
    mapped_column("usuario_id", BigInteger, ForeignKey("usuario.usuario_id"), primary_key=True),
    mapped_column("rol_id", BigInteger, ForeignKey("rol.rol_id"), primary_key=True),
)


# ────────────────────────────────────────────────────────────────────────────────
# Tabla: usuario
# ────────────────────────────────────────────────────────────────────────────────
class Usuario(Base):
    __tablename__ = "usuario"

    usuario_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(190), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(CHAR(1), nullable=False, default="a", server_default="a")
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default="CURRENT_TIMESTAMP")

    # ─────────────────────────────────────────────
    # Relaciones directas
    # ─────────────────────────────────────────────
    roles: Mapped[List["Rol"]] = relationship(
        "Rol", secondary=usuario_rol, back_populates="usuarios", lazy="selectin"
    )

    granjas: Mapped[List["UsuarioGranja"]] = relationship(
        "UsuarioGranja", back_populates="usuario", cascade="all, delete-orphan", lazy="selectin"
    )

    reset_tokens: Mapped[List["PasswordResetToken"]] = relationship(
        "PasswordResetToken", back_populates="usuario", cascade="all, delete-orphan", lazy="selectin"
    )

    # Biometrías y cambios de SOB
    biometrias_creadas: Mapped[List["Biometria"]] = relationship(
        "Biometria", back_populates="creador", cascade="all, delete-orphan", lazy="selectin"
    )
    sob_cambios: Mapped[List["SobCambioLog"]] = relationship(
        "SobCambioLog", back_populates="usuario", cascade="all, delete-orphan", lazy="selectin"
    )

    # ─────────────────────────────────────────────
    # Relaciones con proyecciones y parámetros
    # ─────────────────────────────────────────────
    proyecciones_creadas: Mapped[List["Proyeccion"]] = relationship(
        "Proyeccion", back_populates="creador", lazy="selectin"
    )
    parametros_actualizados: Mapped[List["ParametroCicloVersion"]] = relationship(
        "ParametroCicloVersion", back_populates="usuario", lazy="selectin"
    )

    # ─────────────────────────────────────────────
    # Relaciones con siembras
    # ─────────────────────────────────────────────
    siembras_planes_creados: Mapped[List["SiembraPlan"]] = relationship(
        "SiembraPlan", back_populates="creador", lazy="selectin"
    )
    siembras_estanques_creados: Mapped[List["SiembraEstanque"]] = relationship(
        "SiembraEstanque", back_populates="creador", lazy="selectin"
    )
    siembras_fechas_logs: Mapped[List["SiembraFechaLog"]] = relationship(
        "SiembraFechaLog", back_populates="usuario", lazy="selectin"
    )

    # ─────────────────────────────────────────────
    # Relaciones con cosechas
    # ─────────────────────────────────────────────
    planes_cosechas_creados: Mapped[List["PlanCosechas"]] = relationship(
        "PlanCosechas", back_populates="creador", lazy="selectin"
    )
    cosechas_olas_creadas: Mapped[List["CosechaOla"]] = relationship(
        "CosechaOla", back_populates="creador", lazy="selectin"
    )
    cosechas_estanques_creados: Mapped[List["CosechaEstanque"]] = relationship(
        "CosechaEstanque", back_populates="creador", foreign_keys="CosechaEstanque.created_by", lazy="selectin"
    )
    cosechas_estanques_confirmados: Mapped[List["CosechaEstanque"]] = relationship(
        "CosechaEstanque", back_populates="confirmador", foreign_keys="CosechaEstanque.confirmado_por", lazy="selectin"
    )
    cosechas_fechas_logs: Mapped[List["CosechaFechaLog"]] = relationship(
        "CosechaFechaLog", back_populates="usuario", lazy="selectin"
    )

    # ─────────────────────────────────────────────
    # Relaciones con tareas
    # ─────────────────────────────────────────────
    tareas_creadas: Mapped[List["Tarea"]] = relationship(
        "Tarea", back_populates="creador", foreign_keys="Tarea.created_by", lazy="selectin"
    )
    tareas_asignadas: Mapped[List["Tarea"]] = relationship(
        "Tarea", back_populates="asignado", foreign_keys="Tarea.asignado_a", lazy="selectin"
    )

    archivos_subidos: Mapped[list["Archivo"]] = relationship(
        "Archivo", back_populates="usuario", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_usuario_email"),
        CheckConstraint("estado in ('a','i')", name="usuario_chk_estado"),
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.usuario_id} email={self.email!r} estado={self.estado!r}>"


# ────────────────────────────────────────────────────────────────────────────────
# Tabla: rol
# ────────────────────────────────────────────────────────────────────────────────
class Rol(Base):
    __tablename__ = "rol"

    rol_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    usuarios: Mapped[List[Usuario]] = relationship(
        "Usuario", secondary=usuario_rol, back_populates="roles", lazy="selectin"
    )

    __table_args__ = (UniqueConstraint("nombre", name="uq_rol_nombre"),)

    def __repr__(self) -> str:
        return f"<Rol id={self.rol_id} nombre={self.nombre!r}>"


# ────────────────────────────────────────────────────────────────────────────────
# Tabla: usuario_granja
# ────────────────────────────────────────────────────────────────────────────────
class UsuarioGranja(Base):
    __tablename__ = "usuario_granja"

    usuario_granja_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False, index=True)
    granja_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("granja.granja_id"), nullable=False, index=True)
    estado: Mapped[str] = mapped_column(CHAR(1), nullable=False, default="a", server_default="a")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default="CURRENT_TIMESTAMP")

    usuario: Mapped[Usuario] = relationship("Usuario", back_populates="granjas")
    granja: Mapped["Granja"] = relationship("Granja", back_populates="usuarios")

    __table_args__ = (
        UniqueConstraint("usuario_id", "granja_id", name="uq_usuario_granja"),
        CheckConstraint("estado in ('a','i')", name="usuario_granja_chk_estado"),
        Index("ix_ug_granja", "granja_id"),
    )

    def __repr__(self) -> str:
        return f"<UsuarioGranja id={self.usuario_granja_id} usuario_id={self.usuario_id} granja_id={self.granja_id} estado={self.estado!r}>"


# ────────────────────────────────────────────────────────────────────────────────
# Tabla: password_reset_token
# ────────────────────────────────────────────────────────────────────────────────
class PasswordResetToken(Base):
    __tablename__ = "password_reset_token"

    token_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expira_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default="CURRENT_TIMESTAMP")

    usuario: Mapped[Usuario] = relationship("Usuario", back_populates="reset_tokens")

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_prt_token"),
        Index("ix_prt_usuario", "usuario_id"),
    )

    def __repr__(self) -> str:
        return f"<PasswordResetToken id={self.token_id} usuario_id={self.usuario_id}>"
