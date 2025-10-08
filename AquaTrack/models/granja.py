from sqlalchemy import Column, BigInteger, String, Text, DateTime, Numeric
from sqlalchemy.sql import func
from utils.db import Base

class Granja(Base):
    __tablename__ = "granja"
    granja_id = Column(BigInteger, primary_key=True, autoincrement=True)
    nombre = Column(String(150), nullable=False)
    ubicacion = Column(String(200))
    descripcion = Column(Text)
    superficie_total_m2 = Column(Numeric(14, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
