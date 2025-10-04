from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class UsuarioGranja(Base):
    __tablename__ = "usuario_granja"

    usuario_granja_id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.usuario_id"), nullable=False)
    granja_id: Mapped[int] = mapped_column(ForeignKey("granja.granja_id"), nullable=False)
    estado: Mapped[str] = mapped_column(CHAR(1), default="a", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    usuario: Mapped["Usuario"] = relationship(back_populates="granjas")
    granja: Mapped["Granja"] = relationship(back_populates="usuarios")
