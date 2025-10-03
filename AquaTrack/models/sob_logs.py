from sqlalchemy import Column, BigInteger, DECIMAL, String, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class SOBCambioLog(Base):
    __tablename__ = "sob_cambio_log"

    sob_cambio_log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    estanque_id = Column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False)
    ciclo_id = Column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False)
    sob_anterior_pct = Column(DECIMAL(5,2), nullable=False)
    sob_nueva_pct = Column(DECIMAL(5,2), nullable=False)
    fuente = Column(Enum("operativa_actual", "ajuste_manual", "reforecast", name="sob_fuente_enum"), nullable=False)
    motivo = Column(String(255))
    changed_by = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at = Column(DateTime, server_default=func.now(), nullable=False)

    estanque = relationship("Estanque", back_populates="sob_cambios")
    ciclo = relationship("Ciclo", back_populates="sob_cambios")
    user = relationship("Usuario", back_populates="sob_cambios")
