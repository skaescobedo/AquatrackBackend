from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, DateTime, CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class Usuario(Base):
    __tablename__ = "usuario"

    usuario_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(30), nullable=False)
    apellido1: Mapped[str] = mapped_column(String(30), nullable=False)
    apellido2: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(CHAR(1), default="a", nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    roles: Mapped[List["UsuarioRol"]] = relationship(back_populates="usuario", cascade="all, delete-orphan")
    granjas: Mapped[List["UsuarioGranja"]] = relationship(back_populates="usuario", cascade="all, delete-orphan")
    reset_tokens: Mapped[List["PasswordResetToken"]] = relationship(back_populates="usuario", cascade="all, delete-orphan")

    # creador/confirmador en varias tablas:
    tareas_creadas: Mapped[List["Tarea"]] = relationship(back_populates="creador")
    archivos_subidos: Mapped[List["Archivo"]] = relationship(back_populates="uploader")
    proyecciones_creadas: Mapped[List["Proyeccion"]] = relationship(back_populates="creador")
    siembra_estanque_creadas: Mapped[List["SiembraEstanque"]] = relationship(back_populates="creador")
    siembra_fecha_cambios: Mapped[List["SiembraFechaLog"]] = relationship(back_populates="autor_cambio")
    planes_cosecha_creados: Mapped[List["PlanCosechas"]] = relationship(back_populates="creador")
    olas_creadas: Mapped[List["CosechaOla"]] = relationship(back_populates="creador")
    cosechas_creadas: Mapped[List["CosechaEstanque"]] = relationship(back_populates="creador")
    cosechas_confirmadas: Mapped[List["CosechaEstanque"]] = relationship(back_populates="confirmador", foreign_keys="CosechaEstanque.confirmado_por")
    cosecha_fecha_cambios: Mapped[List["CosechaFechaLog"]] = relationship(back_populates="autor_cambio")
    biometrias_creadas: Mapped[List["Biometria"]] = relationship(back_populates="creador")
    sob_cambios: Mapped[List["SobCambioLog"]] = relationship(back_populates="autor_cambio")
