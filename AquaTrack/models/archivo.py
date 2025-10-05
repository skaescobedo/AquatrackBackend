from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, DateTime, ForeignKey, CHAR, text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


class Archivo(Base):
    __tablename__ = "archivo"

    archivo_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    nombre_original: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo_mime: Mapped[str] = mapped_column(String(120), nullable=False)
    tamanio_bytes: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(300), nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(CHAR(64), unique=True)
    subido_por: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("usuario.usuario_id"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    uploader: Mapped[Optional["Usuario"]] = relationship(
        back_populates="archivos_subidos",
        foreign_keys=[subido_por],
    )
    proyecciones: Mapped[List["ArchivoProyeccion"]] = relationship(
        back_populates="archivo",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
