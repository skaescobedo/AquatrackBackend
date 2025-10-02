from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    BigInteger, Date, DateTime, DECIMAL, ForeignKey, String, text, CheckConstraint, Enum as SqlEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.cycle import Ciclo
    from models.farm import Estanque
    from models.user import Usuario


# ───────────────────────────────────────────────────────────────────────────────
# Enums de Python (opcional, para claridad en código)
# ───────────────────────────────────────────────────────────────────────────────
class SobFuente(str, Enum):
    OPERATIVA_ACTUAL = "operativa_actual"
    AJUSTE_MANUAL = "ajuste_manual"
    REFORECAST = "reforecast"


# ───────────────────────────────────────────────────────────────────────────────
# Tabla: biometria
# ───────────────────────────────────────────────────────────────────────────────
class Biometria(Base):
    __tablename__ = "biometria"

    biometria_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo.ciclo_id", name="fk_bio_ciclo"), nullable=False)
    estanque_id: Mapped[int] = mapped_column(ForeignKey("estanque.estanque_id", name="fk_bio_estanque"), nullable=False)

    fecha: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    n_muestra: Mapped[int] = mapped_column(nullable=False)
    peso_muestra_g: Mapped[float] = mapped_column(DECIMAL(10, 3), nullable=False)
    pp_g: Mapped[float] = mapped_column(DECIMAL(7, 3), nullable=False)
    sob_usada_pct: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    incremento_g_sem: Mapped[Optional[float]] = mapped_column(DECIMAL(7, 3))
    notas: Mapped[Optional[str]] = mapped_column(String(255))

    actualiza_sob_operativa: Mapped[bool] = mapped_column(default=False, server_default=text("0"))
    sob_fuente: Mapped[Optional[SobFuente]] = mapped_column(SqlEnum(SobFuente))

    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuario.usuario_id", name="fk_bio_user"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    # ───── Relaciones
    ciclo: Mapped["Ciclo"] = relationship("Ciclo", back_populates="biometrias")
    estanque: Mapped["Estanque"] = relationship("Estanque", back_populates="biometrias")
    creador: Mapped[Optional["Usuario"]] = relationship("Usuario", back_populates="biometrias_creadas")

    __table_args__ = (
        CheckConstraint("n_muestra > 0", name="bio_chk_nmuestra"),
        CheckConstraint("peso_muestra_g >= 0", name="bio_chk_peso_muestra"),
        CheckConstraint("pp_g >= 0", name="bio_chk_ppg"),
        CheckConstraint("sob_usada_pct >= 0 AND sob_usada_pct <= 100", name="bio_chk_sob_usada"),
    )


# ───────────────────────────────────────────────────────────────────────────────
# Tabla: sob_cambio_log
# ───────────────────────────────────────────────────────────────────────────────
class SobCambioLog(Base):
    __tablename__ = "sob_cambio_log"

    sob_cambio_log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    estanque_id: Mapped[int] = mapped_column(ForeignKey("estanque.estanque_id", name="fk_soblog_estanque"), nullable=False)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo.ciclo_id", name="fk_soblog_ciclo"), nullable=False)

    sob_anterior_pct: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    sob_nueva_pct: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)

    fuente: Mapped[SobFuente] = mapped_column(SqlEnum(SobFuente), nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String(255))

    changed_by: Mapped[int] = mapped_column(ForeignKey("usuario.usuario_id", name="fk_soblog_user"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # ───── Relaciones
    ciclo: Mapped["Ciclo"] = relationship("Ciclo", back_populates="sob_cambios")
    estanque: Mapped["Estanque"] = relationship("Estanque", back_populates="sob_cambios")
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="sob_cambios")

    __table_args__ = (
        CheckConstraint("sob_anterior_pct >= 0 AND sob_anterior_pct <= 100", name="soblog_chk_sob_anterior"),
        CheckConstraint("sob_nueva_pct >= 0 AND sob_nueva_pct <= 100", name="soblog_chk_sob_nueva"),
    )
