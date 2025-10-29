# models/projection.py
from __future__ import annotations

from datetime import datetime, date
from sqlalchemy import (
    BigInteger, Date, DateTime, ForeignKey, String, Numeric, CHAR, Integer, Boolean, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum

from utils.db import Base
from utils.datetime_utils import now_mazatlan


class SourceType(str, Enum):
    PLANES = "planes"
    ARCHIVO = "archivo"
    REFORECAST = "reforecast"

    @classmethod
    def _missing_(cls, value):
        """Permitir que SQLAlchemy mapée valores independientemente del case"""
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None



class Proyeccion(Base):
    __tablename__ = "proyeccion"

    proyeccion_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False, index=True)

    # Versionamiento
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255))

    # Estado: 'b' borrador, 'p' publicada, 'r' revisión, 'x' cancelada
    status: Mapped[str] = mapped_column(CHAR(1), default="b", nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    creada_por: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario.usuario_id"))

    # Origen de datos
    source_type: Mapped[str | None] = mapped_column(
        SQLEnum(SourceType, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=True
    )

    source_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Trazabilidad de versiones
    parent_version_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("proyeccion.proyeccion_id"))

    # Parámetros objetivo
    sob_final_objetivo_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    siembra_ventana_fin: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now_mazatlan, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now_mazatlan, onupdate=now_mazatlan,
                                                 nullable=False)

    # Relationships
    ciclo: Mapped["Ciclo"] = relationship("Ciclo", foreign_keys=[ciclo_id])
    creador: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[creada_por])
    parent_version: Mapped["Proyeccion | None"] = relationship(
        "Proyeccion",
        remote_side=[proyeccion_id],
        foreign_keys=[parent_version_id]
    )
    lineas: Mapped[list["ProyeccionLinea"]] = relationship(
        "ProyeccionLinea",
        back_populates="proyeccion",
        cascade="all, delete-orphan"
    )


class ProyeccionLinea(Base):
    __tablename__ = "proyeccion_linea"

    proyeccion_linea_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    proyeccion_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("proyeccion.proyeccion_id"), nullable=False,
                                               index=True)

    # Datos temporales
    edad_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    semana_idx: Mapped[int] = mapped_column(Integer, nullable=False)  # 0, 1, 2, ...
    fecha_plan: Mapped[date] = mapped_column(Date, nullable=False)

    # Datos biométricos proyectados
    pp_g: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)
    incremento_g_sem: Mapped[float | None] = mapped_column(Numeric(7, 3))
    sob_pct_linea: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    # Marcador de cosecha
    cosecha_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retiro_org_m2: Mapped[float | None] = mapped_column(Numeric(12, 4))

    nota: Mapped[str | None] = mapped_column(String(255))

    # Relationships
    proyeccion: Mapped["Proyeccion"] = relationship("Proyeccion", back_populates="lineas")