from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class PasswordResetToken(Base):
    __tablename__ = "password_reset_token"

    token_id = Column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    expira_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    usuario = relationship("Usuario", back_populates="pass_resets")
