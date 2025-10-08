# models/plan_cosechas.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


class PlanCosechas(Base):
    __tablename__ = "plan_cosechas"
    __table_args__ = (
        UniqueConstraint("ciclo_id", name="uq_plan_cosechas_por_ciclo"),
        Index("ix_pc_created_at", "created_at"),
    )

    plan_cosechas_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    ciclo_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("ciclo.ciclo_id"), nullable=False)
    nota_operativa: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(BIGINT(unsigned=True), ForeignKey("usuario.usuario_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False
    )

    ciclo: Mapped["Ciclo"] = relationship(back_populates="plan_cosechas")
    creador: Mapped[Optional["Usuario"]] = relationship(
        back_populates="planes_cosecha_creados",
        foreign_keys=[created_by],
    )
    olas: Mapped[List["CosechaOla"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
