from sqlalchemy import Column, BigInteger, String, DateTime, Date, CHAR, Boolean, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class Proyeccion(Base):
    __tablename__ = "proyeccion"

    proyeccion_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id = Column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False)
    version = Column(String(20), nullable=False)
    descripcion = Column(String(255))
    status = Column(CHAR(1), nullable=False, default="b")  # b/p/r/x
    is_current = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime)
    creada_por = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    source_type = Column(Enum("auto", "archivo", "reforecast", name="proy_source_enum"))
    source_ref = Column(String(120))
    parent_version_id = Column(BigInteger, ForeignKey("proyeccion.proyeccion_id"))
    siembra_ventana_inicio = Column(Date)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    ciclo = relationship("Ciclo", back_populates="proyecciones")
    creador = relationship("Usuario", back_populates="proyecciones_creadas")
    parent = relationship("Proyeccion", remote_side=[proyeccion_id])
    lineas = relationship("ProyeccionLinea", back_populates="proyeccion", cascade="all, delete-orphan")
    archivos = relationship("ArchivoProyeccion", back_populates="proyeccion")
    parametro_ciclo = relationship("ParametroCicloVersion", back_populates="proyeccion", uselist=False)
    planes_cosecha = relationship("PlanCosechas", back_populates="proyeccion")
