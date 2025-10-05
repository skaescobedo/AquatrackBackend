from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, DateTime, Enum as SAEnum, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from enums.enums import UsuarioEstadoEnum


class Usuario(Base):
    __tablename__ = "usuario"

    usuario_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(30), nullable=False)
    apellido1: Mapped[str] = mapped_column(String(30), nullable=False)
    apellido2: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[UsuarioEstadoEnum] = mapped_column(
        SAEnum(UsuarioEstadoEnum, native_enum=False, length=1, name="usuario_estado_enum"),
        server_default=text("'a'"),
        nullable=False,
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )

    roles: Mapped[List["UsuarioRol"]] = relationship(back_populates="usuario", cascade="all, delete-orphan", lazy="selectin")
    granjas: Mapped[List["UsuarioGranja"]] = relationship(back_populates="usuario", cascade="all, delete-orphan", lazy="selectin")
    reset_tokens: Mapped[List["PasswordResetToken"]] = relationship(back_populates="usuario", cascade="all, delete-orphan", lazy="selectin")

    tareas_creadas: Mapped[List["Tarea"]] = relationship(
        back_populates="creador",
        foreign_keys="[Tarea.created_by]",
        lazy="selectin",
    )
    archivos_subidos: Mapped[List["Archivo"]] = relationship(
        back_populates="uploader",
        foreign_keys="[Archivo.subido_por]",
        lazy="selectin",
    )
    proyecciones_creadas: Mapped[List["Proyeccion"]] = relationship(
        back_populates="creador",
        foreign_keys="[Proyeccion.creada_por]",
        lazy="selectin",
    )
    planes_siembra_creados: Mapped[List["SiembraPlan"]] = relationship(back_populates="creador")
    siembra_estanque_creadas: Mapped[List["SiembraEstanque"]] = relationship(
        back_populates="creador",
        foreign_keys="[SiembraEstanque.created_by]",
        lazy="selectin",
    )
    siembra_fecha_cambios: Mapped[List["SiembraFechaLog"]] = relationship(
        back_populates="autor_cambio",
        foreign_keys="[SiembraFechaLog.changed_by]",
        lazy="selectin",
    )
    planes_cosecha_creados: Mapped[List["PlanCosechas"]] = relationship(
        back_populates="creador",
        foreign_keys="[PlanCosechas.created_by]",
        lazy="selectin",
    )
    olas_creadas: Mapped[List["CosechaOla"]] = relationship(
        back_populates="creador",
        foreign_keys="[CosechaOla.created_by]",
        lazy="selectin",
    )
    cosechas_creadas: Mapped[List["CosechaEstanque"]] = relationship(
        back_populates="creador",
        foreign_keys="[CosechaEstanque.created_by]",
        lazy="selectin",
    )
    cosechas_confirmadas: Mapped[List["CosechaEstanque"]] = relationship(
        back_populates="confirmador",
        foreign_keys="[CosechaEstanque.confirmado_por]",
        lazy="selectin",
    )
    cosecha_fecha_cambios: Mapped[List["CosechaFechaLog"]] = relationship(
        back_populates="autor_cambio",
        foreign_keys="[CosechaFechaLog.changed_by]",
        lazy="selectin",
    )
    biometrias_creadas: Mapped[List["Biometria"]] = relationship(
        back_populates="creador",
        foreign_keys="[Biometria.created_by]",
        lazy="selectin",
    )
    sob_cambios: Mapped[List["SobCambioLog"]] = relationship(
        back_populates="autor_cambio",
        foreign_keys="[SobCambioLog.changed_by]",
        lazy="selectin",
    )
