from sqlalchemy import Column, BigInteger, String, Date, DateTime, Numeric, CHAR, ForeignKey, Index
from sqlalchemy.sql import func
from utils.db import Base

class CosechaOla(Base):
    __tablename__ = "cosecha_ola"
    cosecha_ola_id = Column(BigInteger, primary_key=True, autoincrement=True)
    plan_cosechas_id = Column(BigInteger, ForeignKey("plan_cosechas.plan_cosechas_id"), nullable=False, index=True)
    nombre = Column(String(120), nullable=False)
    tipo = Column(CHAR(1), nullable=False)  # 'p'=precosecha, 'f'=final
    ventana_inicio = Column(Date, nullable=False)
    ventana_fin = Column(Date, nullable=False)
    objetivo_retiro_org_m2 = Column(Numeric(12,4))
    estado = Column(CHAR(1), nullable=False, default="p")  # 'p' planeada, 'r' reprogramada, 'x' cancelada
    orden = Column(BigInteger)
    notas = Column(String(255))
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

Index("ix_ola_plan_estado", CosechaOla.plan_cosechas_id, CosechaOla.estado)
Index("ix_ola_plan_orden", CosechaOla.plan_cosechas_id, CosechaOla.orden)
Index("ix_ola_plan_ventana", CosechaOla.plan_cosechas_id, CosechaOla.ventana_inicio, CosechaOla.ventana_fin)
