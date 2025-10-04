from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class PasswordResetToken(Base):
    __tablename__ = "password_reset_token"

    token_id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.usuario_id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False)
    expira_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    usuario: Mapped["Usuario"] = relationship(back_populates="reset_tokens")
