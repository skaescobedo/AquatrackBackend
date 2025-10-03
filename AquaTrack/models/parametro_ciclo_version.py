from sqlalchemy import Column, BigInteger, DECIMAL, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class ParametroCicloVersion(Base):
    __tablename__ = "parametro_ciclo_version"

    parametro_ciclo_version_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id = Column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False)
    proyeccion_id = Column(BigInteger, ForeignKey("proyeccion.proyeccion_id"), nullable=False)
    sob_actual_pct_snapshot = Column(DECIMAL(5,2), nullable=False)
    sob_final_objetivo_pct = Column(DECIMAL(5,2), nullable=False)
    nota = Column(String(255))
    updated_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    ciclo = relationship("Ciclo")
    proyeccion = relationship("Proyeccion", back_populates="parametro_ciclo")
    updater = relationship("Usuario", back_populates="pcv_actualizados")
