from sqlalchemy import Column, BigInteger, DECIMAL, Integer, Date, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class CicloResumen(Base):
    __tablename__ = "ciclo_resumen"

    ciclo_id = Column(BigInteger, ForeignKey("ciclo.ciclo_id"), primary_key=True)
    sob_final_real_pct = Column(DECIMAL(5,2), nullable=False)
    toneladas_cosechadas = Column(DECIMAL(14,3), nullable=False)
    n_estanques_cosechados = Column(Integer, nullable=False)
    fecha_inicio_real = Column(Date)
    fecha_fin_real = Column(Date)
    notas_cierre = Column(String(255))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    ciclo = relationship("Ciclo", back_populates="resumen")
