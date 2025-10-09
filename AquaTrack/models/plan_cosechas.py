from sqlalchemy import Column, BigInteger, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from utils.db import Base

class PlanCosechas(Base):
    __tablename__ = "plan_cosechas"
    plan_cosechas_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id = Column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False)
    nota_operativa = Column(Text)
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (UniqueConstraint("ciclo_id", name="uq_plan_cosechas_por_ciclo"),)
