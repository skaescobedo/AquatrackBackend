from __future__ import annotations
from datetime import datetime, date
from sqlalchemy import String, BigInteger, Text, DateTime, Date, func, CHAR, ForeignKey, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class Ciclo(Base):
    __tablename__ = "ciclo"

    ciclo_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    granja_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("granja.granja_id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin_planificada: Mapped[date | None] = mapped_column(Date)
    fecha_cierre_real: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(CHAR(1), default="a", nullable=False)
    observaciones: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    granja: Mapped["Granja"] = relationship("Granja", back_populates="ciclos")
    resumen: Mapped["CicloResumen | None"] = relationship("CicloResumen", back_populates="ciclo", uselist=False)
    siembra_plan: Mapped["SiembraPlan | None"] = relationship("SiembraPlan", back_populates="ciclo", uselist=False)  # 👈 AGREGAR


class CicloResumen(Base):
    __tablename__ = "ciclo_resumen"

    ciclo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ciclo.ciclo_id"), primary_key=True)
    sob_final_real_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    toneladas_cosechadas: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    n_estanques_cosechados: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_inicio_real: Mapped[date | None] = mapped_column(Date)
    fecha_fin_real: Mapped[date | None] = mapped_column(Date)
    notas_cierre: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    ciclo: Mapped["Ciclo"] = relationship("Ciclo", back_populates="resumen")