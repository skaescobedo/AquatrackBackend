from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class ArchivoProyeccion(Base):
    __tablename__ = "archivo_proyeccion"

    archivo_proyeccion_id: Mapped[int] = mapped_column(primary_key=True)
    archivo_id: Mapped[int] = mapped_column(ForeignKey("archivo.archivo_id"), nullable=False)
    proyeccion_id: Mapped[int] = mapped_column(ForeignKey("proyeccion.proyeccion_id"), nullable=False)
    proposito: Mapped[str] = mapped_column(Enum("insumo_calculo", "respaldo", "reporte_publicado", "otro", name="ap_proposito"), default="otro", nullable=False)
    notas: Mapped[Optional[str]] = mapped_column(String(255))
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    archivo: Mapped["Archivo"] = relationship(back_populates="proyecciones")
    proyeccion: Mapped["Proyeccion"] = relationship(back_populates="archivos")
