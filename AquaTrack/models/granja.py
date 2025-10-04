from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Text, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class Granja(Base):
    __tablename__ = "granja"

    granja_id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    ubicacion: Mapped[Optional[str]] = mapped_column(String(200))
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    superficie_total_m2: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    usuarios: Mapped[List["UsuarioGranja"]] = relationship(back_populates="granja", cascade="all, delete-orphan")
    estanques: Mapped[List["Estanque"]] = relationship(back_populates="granja", cascade="all, delete-orphan")
    tareas: Mapped[List["Tarea"]] = relationship(back_populates="granja")
    ciclos: Mapped[List["Ciclo"]] = relationship(back_populates="granja")
