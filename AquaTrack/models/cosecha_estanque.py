from sqlalchemy import Column, BigInteger, String, Date, DateTime, Numeric, CHAR, ForeignKey, Index
from sqlalchemy.sql import func
from utils.db import Base

class CosechaEstanque(Base):
    __tablename__ = "cosecha_estanque"
    cosecha_estanque_id = Column(BigInteger, primary_key=True, autoincrement=True)
    estanque_id = Column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False, index=True)
    cosecha_ola_id = Column(BigInteger, ForeignKey("cosecha_ola.cosecha_ola_id"), nullable=False, index=True)
    estado = Column(CHAR(1), nullable=False, default="p")  # 'p' planeada, 'c' confirmada, 'x' cancelada
    fecha_cosecha = Column(Date, nullable=False)
    pp_g = Column(Numeric(7,3))
    biomasa_kg = Column(Numeric(14,3))
    densidad_retirada_org_m2 = Column(Numeric(12,4))
    notas = Column(String(255))
    confirmado_por = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    confirmado_event_at = Column(DateTime)
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

Index("ix_ce_ola_estado", CosechaEstanque.cosecha_ola_id, CosechaEstanque.estado)
Index("ix_ce_ola_fecha", CosechaEstanque.cosecha_ola_id, CosechaEstanque.fecha_cosecha)
Index("ix_ce_created_at", CosechaEstanque.created_at)
