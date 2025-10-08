from sqlalchemy import Column, BigInteger, String, Date, DateTime, CHAR, Text, ForeignKey, Index
from sqlalchemy.sql import func
from utils.db import Base

class Ciclo(Base):
    __tablename__ = "ciclo"
    ciclo_id = Column(BigInteger, primary_key=True, autoincrement=True)
    granja_id = Column(BigInteger, ForeignKey("granja.granja_id"), nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin_planificada = Column(Date)
    fecha_cierre_real = Column(Date)
    estado = Column(CHAR(1), nullable=False, default="a")  # 'a' activo | 't' terminado
    observaciones = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

# Índices adicionales que ya existen en la BD
Index("ix_ciclo_granja_estado", Ciclo.granja_id, Ciclo.estado)
