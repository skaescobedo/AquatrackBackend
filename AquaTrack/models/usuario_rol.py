from __future__ import annotations
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class UsuarioRol(Base):
    __tablename__ = "usuario_rol"

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.usuario_id"), primary_key=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey("rol.rol_id"), primary_key=True)

    usuario: Mapped["Usuario"] = relationship(back_populates="roles")
    rol: Mapped["Rol"] = relationship(back_populates="usuarios")
