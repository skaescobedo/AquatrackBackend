from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from enums.enums import ArchivoPropositoProyeccionEnum


class ArchivoProyeccion(Base):
    __tablename__ = "archivo_proyeccion"

    archivo_proyeccion_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    archivo_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("archivo.archivo_id"), nullable=False)
    proyeccion_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("proyeccion.proyeccion_id"), nullable=False)
    proposito: Mapped[ArchivoPropositoProyeccionEnum] = mapped_column(
        SAEnum(ArchivoPropositoProyeccionEnum, name="ap_proposito", native_enum=True),
        server_default=text("'otro'"),
        nullable=False,
    )
    notas: Mapped[Optional[str]] = mapped_column(String(255))
    linked_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    archivo: Mapped["Archivo"] = relationship(back_populates="proyecciones")
    proyeccion: Mapped["Proyeccion"] = relationship(back_populates="archivos")
