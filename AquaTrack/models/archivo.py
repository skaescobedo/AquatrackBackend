from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, BigInteger, ForeignKey, CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class Archivo(Base):
    __tablename__ = "archivo"

    archivo_id: Mapped[int] = mapped_column(primary_key=True)
    nombre_original: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo_mime: Mapped[str] = mapped_column(String(120), nullable=False)
    tamanio_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(300), nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(CHAR(64))
    subido_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    uploader: Mapped[Optional["Usuario"]] = relationship(back_populates="archivos_subidos")
    proyecciones: Mapped[List["ArchivoProyeccion"]] = relationship(back_populates="archivo", cascade="all, delete-orphan")
