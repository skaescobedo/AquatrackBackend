from sqlalchemy import Column, BigInteger, Integer, Date, DateTime, DECIMAL, String, Enum, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class Biometria(Base):
    __tablename__ = "biometria"

    biometria_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id = Column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False)
    estanque_id = Column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False)
    fecha = Column(Date, nullable=False)
    n_muestra = Column(Integer, nullable=False)
    peso_muestra_g = Column(DECIMAL(10,3), nullable=False)
    pp_g = Column(DECIMAL(7,3), nullable=False)
    sob_usada_pct = Column(DECIMAL(5,2), nullable=False)
    incremento_g_sem = Column(DECIMAL(7,3))
    notas = Column(String(255))
    actualiza_sob_operativa = Column(Boolean, nullable=False, default=False)
    sob_fuente = Column(Enum("operativa_actual", "ajuste_manual", "reforecast", name="bio_sob_fuente"))
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    ciclo = relationship("Ciclo", back_populates="biometrias")
    estanque = relationship("Estanque", back_populates="biometrias")
    creator = relationship("Usuario", back_populates="biometria_creadas")
