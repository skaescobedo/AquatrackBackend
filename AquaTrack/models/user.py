# models/user.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, BigInteger, CHAR, DateTime, Boolean, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from utils.datetime_utils import now_mazatlan


class Usuario(Base):
    __tablename__ = "usuario"

    usuario_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(30), nullable=False)
    apellido1: Mapped[str] = mapped_column(String(30), nullable=False)
    apellido2: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(CHAR(1), default="a", nullable=False)  # a/i
    is_admin_global: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now_mazatlan, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now_mazatlan, onupdate=now_mazatlan,
                                                 nullable=False)

    granjas: Mapped[list[UsuarioGranja]] = relationship(
        "UsuarioGranja", back_populates="usuario", cascade="all, delete-orphan"
    )

    @property
    def nombre_completo(self):
        """Propiedad para devolver el nombre completo."""
        return f"{self.nombre} {self.apellido1}".strip()


class UsuarioGranja(Base):
    """
    Asignación de usuario a granja con rol y scopes.

    Características:
    - Un usuario puede estar en múltiples granjas con roles diferentes
    - Cada asignación tiene scopes (permisos granulares)
    - Scopes por defecto se asignan según el rol
    - Scopes opcionales se pueden agregar/quitar manualmente
    """
    __tablename__ = "usuario_granja"
    __table_args__ = (
        UniqueConstraint("usuario_id", "granja_id", name="uq_usuario_granja"),
    )

    usuario_granja_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuario.usuario_id", ondelete="RESTRICT"),
        nullable=False
    )
    granja_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("granja.granja_id", ondelete="RESTRICT"),
        nullable=False
    )
    rol_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("rol.rol_id", ondelete="RESTRICT"),
        nullable=False
    )

    # Scopes (permisos granulares en formato JSON)
    # Ejemplo: ["gestionar_estanques", "gestionar_ciclos", "gestion_usuarios"]
    scopes: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="Permisos granulares del usuario en esta granja"
    )

    status: Mapped[str] = mapped_column(CHAR(1), default="a", nullable=False)  # a/i
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now_mazatlan, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=now_mazatlan,
        onupdate=now_mazatlan,
        nullable=False
    )

    # Relationships
    usuario: Mapped[Usuario] = relationship("Usuario", back_populates="granjas")