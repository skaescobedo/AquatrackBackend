from sqlalchemy import Column, BigInteger, String, Text, DateTime, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class Granja(Base):
    __tablename__ = "granja"

    granja_id = Column(BigInteger, primary_key=True, autoincrement=True)
    nombre = Column(String(150), nullable=False)
    ubicacion = Column(String(200))
    descripcion = Column(Text)
    superficie_total_m2 = Column(DECIMAL(14,2), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    estanques = relationship("Estanque", back_populates="granja")
    ciclos = relationship("Ciclo", back_populates="granja")
    usuarios = relationship("UsuarioGranja", back_populates="granja", cascade="all, delete-orphan")
