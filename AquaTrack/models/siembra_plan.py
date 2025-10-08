from sqlalchemy import Column, BigInteger, Date, DateTime, Numeric, Text, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from utils.db import Base

class SiembraPlan(Base):
    __tablename__ = "siembra_plan"
    siembra_plan_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id = Column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False)
    ventana_inicio = Column(Date, nullable=False)
    ventana_fin = Column(Date, nullable=False)
    densidad_org_m2 = Column(Numeric(12,4), nullable=False)
    talla_inicial_g = Column(Numeric(7,3), nullable=False)
    observaciones = Column(Text)
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    __table_args__ = (UniqueConstraint("ciclo_id", name="uq_sp_por_ciclo"),)
