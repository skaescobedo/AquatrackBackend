from sqlalchemy import Column, BigInteger, DateTime, Numeric, String, Enum, ForeignKey, Index
from sqlalchemy.sql import func
from utils.db import Base

class SobCambioLog(Base):
    __tablename__ = "sob_cambio_log"
    sob_cambio_log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    estanque_id = Column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False)
    ciclo_id = Column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False)
    sob_anterior_pct = Column(Numeric(5,2), nullable=False)
    sob_nueva_pct = Column(Numeric(5,2), nullable=False)
    fuente = Column(Enum('operativa_actual','ajuste_manual','reforecast', name='sob_log_fuente_enum'), nullable=False)
    motivo = Column(String(255))
    changed_by = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

Index("ix_soblog_estanque_ciclo", SobCambioLog.estanque_id, SobCambioLog.ciclo_id)
