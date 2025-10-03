from sqlalchemy import Column, BigInteger, String, Date, DateTime, Text, CHAR, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class Ciclo(Base):
    __tablename__ = "ciclo"

    ciclo_id = Column(BigInteger, primary_key=True, autoincrement=True)
    granja_id = Column(BigInteger, ForeignKey("granja.granja_id"), nullable=False)
    nombre = Column(String(150), nullable=False)
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin_planificada = Column(Date)
    fecha_cierre_real = Column(Date)
    estado = Column(CHAR(1), nullable=False, default="a")  # a/c
    observaciones = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    granja = relationship("Granja", back_populates="ciclos")
    proyecciones = relationship("Proyeccion", back_populates="ciclo")
    siembra_plan = relationship("SiembraPlan", back_populates="ciclo", uselist=False)
    plan_cosechas = relationship("PlanCosechas", back_populates="ciclo", uselist=False)
    biometrias = relationship("Biometria", back_populates="ciclo")
    sob_cambios = relationship("SOBCambioLog", back_populates="ciclo")
    resumen = relationship("CicloResumen", back_populates="ciclo", uselist=False)
