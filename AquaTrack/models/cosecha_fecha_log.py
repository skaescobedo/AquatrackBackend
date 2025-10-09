from sqlalchemy import Column, BigInteger, Date, DateTime, String, ForeignKey, Index
from sqlalchemy.sql import func
from utils.db import Base

class CosechaFechaLog(Base):
    __tablename__ = "cosecha_fecha_log"
    cosecha_fecha_log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cosecha_estanque_id = Column(BigInteger, ForeignKey("cosecha_estanque.cosecha_estanque_id"), nullable=False)
    fecha_anterior = Column(Date, nullable=False)
    fecha_nueva = Column(Date, nullable=False)
    motivo = Column(String(255))
    changed_by = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

Index("ix_cfl_ce_changed_at", CosechaFechaLog.cosecha_estanque_id, CosechaFechaLog.changed_at)
