from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, BigInteger, Text, DateTime, func, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class Granja(Base):
    __tablename__ = "granja"

    granja_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    ubicacion: Mapped[str | None] = mapped_column(String(200))
    descripcion: Mapped[str | None] = mapped_column(Text())
    superficie_total_m2: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    estanques: Mapped[list["Estanque"]] = relationship(
        "Estanque", back_populates="granja", cascade="all, delete-orphan", passive_deletes=False
    )
    ciclos: Mapped[list["Ciclo"]] = relationship(  # 👈 ESTO FALTABA
        "Ciclo", back_populates="granja", cascade="all, delete-orphan"
    )