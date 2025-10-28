from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, BigInteger, DateTime, func, Numeric, CHAR, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base

class Estanque(Base):
    __tablename__ = "estanque"

    estanque_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    granja_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("granja.granja_id", ondelete="RESTRICT"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    superficie_m2: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(CHAR(1), default="i", nullable=False)  # i/a/c/m
    is_vigente: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    granja: Mapped["Granja"] = relationship("Granja", back_populates="estanques")
