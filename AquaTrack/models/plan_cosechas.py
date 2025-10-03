from sqlalchemy import Column, BigInteger, String, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class PlanCosechas(Base):
    __tablename__ = "plan_cosechas"

    plan_cosechas_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id = Column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False)
    proyeccion_id = Column(BigInteger, ForeignKey("proyeccion.proyeccion_id"), nullable=False)
    nombre = Column(String(120), nullable=False)
    fecha_inicio_plan = Column(Date, nullable=False)
    fecha_fin_plan = Column(Date, nullable=False)
    nota_operativa = Column(String(255))
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    ciclo = relationship("Ciclo", back_populates="plan_cosechas")
    proyeccion = relationship("Proyeccion", back_populates="planes_cosecha")
    creador = relationship("Usuario")
    olas = relationship("CosechaOla", back_populates="plan", cascade="all, delete-orphan")
    archivos = relationship("ArchivoPlanCosechas", back_populates="plan_cosechas")
