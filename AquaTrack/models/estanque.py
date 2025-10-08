from sqlalchemy import Column, BigInteger, String, DateTime, Numeric, CHAR, ForeignKey, Index
from sqlalchemy.sql import func
from utils.db import Base

class Estanque(Base):
    __tablename__ = "estanque"
    estanque_id = Column(BigInteger, primary_key=True, autoincrement=True)
    granja_id = Column(BigInteger, ForeignKey("granja.granja_id"), nullable=False, index=True)
    nombre = Column(String(120), nullable=False)
    superficie_m2 = Column(Numeric(14, 2), nullable=False)
    status = Column(CHAR(1), nullable=False, default="i")
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

Index("ix_estanque_status", Estanque.status)
