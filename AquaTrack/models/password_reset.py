# models/password_reset.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, CHAR, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


class PasswordResetToken(Base):
    """
    Modelo para tokens de recuperación de contraseña.

    Características:
    - Token hash único (SHA-256)
    - Expira después de N minutos (configurable)
    - Se marca como usado al resetear contraseña
    - Se limpia automáticamente tokens expirados
    """
    __tablename__ = "password_reset_token"

    token_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuario.usuario_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    token_hash: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False)
    expira_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    # Relationship
    usuario: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[usuario_id])