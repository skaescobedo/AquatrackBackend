from __future__ import annotations
from typing import List

from sqlalchemy import String
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


class Rol(Base):
    __tablename__ = "rol"

    rol_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255))

    usuarios: Mapped[List["UsuarioRol"]] = relationship(back_populates="rol", cascade="all, delete-orphan", lazy="selectin")
