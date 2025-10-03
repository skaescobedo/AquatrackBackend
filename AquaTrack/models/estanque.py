from sqlalchemy import Column, BigInteger, String, DateTime, DECIMAL, CHAR, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class Estanque(Base):
    __tablename__ = "estanque"

    estanque_id = Column(BigInteger, primary_key=True, autoincrement=True)
    granja_id = Column(BigInteger, ForeignKey("granja.granja_id"), nullable=False)
    nombre = Column(String(120), nullable=False)
    superficie_m2 = Column(DECIMAL(14,2), nullable=False)
    status = Column(CHAR(1), nullable=False, default="i")  # i,a,c,m
    sob_estanque_pct = Column(DECIMAL(5,2), nullable=False, default=100.00)
    sob_updated_at = Column(DateTime)
    sob_updated_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    sob_source = Column(Enum("general", "manual", "reforecast", name="sob_source_enum"))
    sob_note = Column(String(255))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    granja = relationship("Granja", back_populates="estanques")
    biometrias = relationship("Biometria", back_populates="estanque")
    siembras = relationship("SiembraEstanque", back_populates="estanque")
    cosechas = relationship("CosechaEstanque", back_populates="estanque")
    sob_cambios = relationship("SOBCambioLog", back_populates="estanque")
