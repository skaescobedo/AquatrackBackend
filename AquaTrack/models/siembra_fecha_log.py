from sqlalchemy import Column, BigInteger, Date, DateTime, String, ForeignKey, Index
from sqlalchemy.sql import func
from utils.db import Base

class SiembraFechaLog(Base):
    __tablename__ = "siembra_fecha_log"
    siembra_fecha_log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    siembra_estanque_id = Column(BigInteger, ForeignKey("siembra_estanque.siembra_estanque_id"), nullable=False)
    fecha_anterior = Column(Date)
    fecha_nueva = Column(Date, nullable=False)
    motivo = Column(String(255))
    changed_by = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

Index("ix_sfl_se", SiembraFechaLog.siembra_estanque_id)
Index("ix_sfl_se_changed", SiembraFechaLog.siembra_estanque_id, SiembraFechaLog.changed_at)
