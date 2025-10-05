from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Text, DateTime, text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


class Granja(Base):
    __tablename__ = "granja"

    granja_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    ubicacion: Mapped[Optional[str]] = mapped_column(String(200))
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    superficie_total_m2: Mapped[float] = mapped_column(DECIMAL(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )

    usuarios: Mapped[List["UsuarioGranja"]] = relationship(back_populates="granja", cascade="all, delete-orphan", lazy="selectin")
    estanques: Mapped[List["Estanque"]] = relationship(back_populates="granja", cascade="all, delete-orphan", lazy="selectin")
    tareas: Mapped[List["Tarea"]] = relationship(back_populates="granja", lazy="selectin")
    ciclos: Mapped[List["Ciclo"]] = relationship(back_populates="granja", lazy="selectin")
