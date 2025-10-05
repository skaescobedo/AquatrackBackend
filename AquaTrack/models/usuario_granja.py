from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base
from enums.enums import UsuarioEstadoEnum


class UsuarioGranja(Base):
    __tablename__ = "usuario_granja"

    usuario_granja_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("usuario.usuario_id"), nullable=False)
    granja_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("granja.granja_id"), nullable=False)
    estado: Mapped[UsuarioEstadoEnum] = mapped_column(
        SAEnum(UsuarioEstadoEnum, native_enum=False, length=1, name="usuario_granja_estado_enum"),
        server_default=text("'a'"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="granjas")
    granja: Mapped["Granja"] = relationship(back_populates="usuarios")
