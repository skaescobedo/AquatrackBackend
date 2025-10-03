from sqlalchemy import Column, BigInteger, String, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class ArchivoPlanCosechas(Base):
    __tablename__ = "archivo_plan_cosechas"

    archivo_plan_cosechas_id = Column(BigInteger, primary_key=True, autoincrement=True)
    archivo_id = Column(BigInteger, ForeignKey("archivo.archivo_id"), nullable=False)
    plan_cosechas_id = Column(BigInteger, ForeignKey("plan_cosechas.plan_cosechas_id"), nullable=False)
    proposito = Column(Enum("plantilla", "respaldo", "otro", name="apc_proposito"), nullable=False, default="plantilla")
    notas = Column(String(255))
    linked_at = Column(DateTime, server_default=func.now(), nullable=False)

    archivo = relationship("Archivo", back_populates="plan_cosechas")
    plan_cosechas = relationship("PlanCosechas", back_populates="archivos")

class ArchivoProyeccion(Base):
    __tablename__ = "archivo_proyeccion"

    archivo_proyeccion_id = Column(BigInteger, primary_key=True, autoincrement=True)
    archivo_id = Column(BigInteger, ForeignKey("archivo.archivo_id"), nullable=False)
    proyeccion_id = Column(BigInteger, ForeignKey("proyeccion.proyeccion_id"), nullable=False)
    proposito = Column(Enum("insumo_calculo", "respaldo", "reporte_publicado", "otro", name="ap_proposito"),
                       nullable=False, default="otro")
    notas = Column(String(255))
    linked_at = Column(DateTime, server_default=func.now(), nullable=False)

    archivo = relationship("Archivo", back_populates="proyecciones")
    proyeccion = relationship("Proyeccion", back_populates="archivos")

class ArchivoSiembraPlan(Base):
    __tablename__ = "archivo_siembra_plan"

    archivo_siembra_plan_id = Column(BigInteger, primary_key=True, autoincrement=True)
    archivo_id = Column(BigInteger, ForeignKey("archivo.archivo_id"), nullable=False)
    siembra_plan_id = Column(BigInteger, ForeignKey("siembra_plan.siembra_plan_id"), nullable=False)
    proposito = Column(Enum("plantilla", "respaldo", "otro", name="asp_proposito"),
                       nullable=False, default="plantilla")
    notas = Column(String(255))
    linked_at = Column(DateTime, server_default=func.now(), nullable=False)

    archivo = relationship("Archivo", back_populates="siembra_planes")
    siembra_plan = relationship("SiembraPlan", back_populates="archivos")
