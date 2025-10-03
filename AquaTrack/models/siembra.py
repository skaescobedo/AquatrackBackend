from sqlalchemy import Column, BigInteger, Date, Text, DECIMAL, String, CHAR, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class SiembraPlan(Base):
    __tablename__ = "siembra_plan"

    siembra_plan_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id = Column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False)
    ventana_inicio = Column(Date, nullable=False)
    ventana_fin = Column(Date, nullable=False)
    densidad_org_m2 = Column(DECIMAL(12,4), nullable=False)
    talla_inicial_g = Column(DECIMAL(7,3), nullable=False)
    observaciones = Column(Text)
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    ciclo = relationship("Ciclo", back_populates="siembra_plan")
    creator = relationship("Usuario", back_populates="siembra_plan_creados")
    estanques = relationship("SiembraEstanque", back_populates="plan", cascade="all, delete-orphan")
    archivos = relationship("ArchivoSiembraPlan", back_populates="siembra_plan")

class SiembraEstanque(Base):
    __tablename__ = "siembra_estanque"

    siembra_estanque_id = Column(BigInteger, primary_key=True, autoincrement=True)
    siembra_plan_id = Column(BigInteger, ForeignKey("siembra_plan.siembra_plan_id"), nullable=False)
    estanque_id = Column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False)
    estado = Column(CHAR(1), nullable=False, default="p")  # p/f
    fecha_tentativa = Column(Date)
    fecha_siembra = Column(Date)
    lote = Column(String(80))
    densidad_override_org_m2 = Column(DECIMAL(12,4))
    talla_inicial_override_g = Column(DECIMAL(7,3))
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    plan = relationship("SiembraPlan", back_populates="estanques")
    estanque = relationship("Estanque", back_populates="siembras")
    creator = relationship("Usuario", back_populates="siembras_creadas")
    cambios_fecha = relationship("SiembraFechaLog", back_populates="siembra", cascade="all, delete-orphan")

class SiembraFechaLog(Base):
    __tablename__ = "siembra_fecha_log"

    siembra_fecha_log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    siembra_estanque_id = Column(BigInteger, ForeignKey("siembra_estanque.siembra_estanque_id"), nullable=False)
    fecha_anterior = Column(Date, nullable=False)
    fecha_nueva = Column(Date, nullable=False)
    motivo = Column(String(255))
    changed_by = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at = Column(DateTime, server_default=func.now(), nullable=False)

    siembra = relationship("SiembraEstanque", back_populates="cambios_fecha")
    user = relationship("Usuario")
