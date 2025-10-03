from sqlalchemy import Column, BigInteger, String, Date, DateTime, DECIMAL, CHAR, ForeignKey, Integer
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class CosechaOla(Base):
    __tablename__ = "cosecha_ola"

    cosecha_ola_id = Column(BigInteger, primary_key=True, autoincrement=True)
    plan_cosechas_id = Column(BigInteger, ForeignKey("plan_cosechas.plan_cosechas_id"), nullable=False)
    nombre = Column(String(120), nullable=False)
    tipo = Column(CHAR(1), nullable=False)  # p/f
    ventana_inicio = Column(Date, nullable=False)
    ventana_fin = Column(Date, nullable=False)
    objetivo_retiro_org_m2 = Column(DECIMAL(12,4))
    estado = Column(CHAR(1), nullable=False, default="p")  # p/r/x
    orden = Column(Integer)
    notas = Column(String(255))
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    plan = relationship("PlanCosechas", back_populates="olas")
    creator = relationship("Usuario", back_populates="cosecha_olas_creadas")
    cosechas = relationship("CosechaEstanque", back_populates="ola", cascade="all, delete-orphan")

class CosechaEstanque(Base):
    __tablename__ = "cosecha_estanque"

    cosecha_estanque_id = Column(BigInteger, primary_key=True, autoincrement=True)
    estanque_id = Column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False)
    cosecha_ola_id = Column(BigInteger, ForeignKey("cosecha_ola.cosecha_ola_id"), nullable=False)
    tipo = Column(CHAR(1), nullable=False)   # p/f
    estado = Column(CHAR(1), nullable=False, default="p")  # p/r/c/x
    fecha_cosecha = Column(Date, nullable=False)
    pp_g = Column(DECIMAL(7,3))
    biomasa_kg = Column(DECIMAL(14,3))
    densidad_retirada_org_m2 = Column(DECIMAL(12,4))
    notas = Column(String(255))
    confirmado_por = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    confirmado_event_at = Column(DateTime)
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    estanque = relationship("Estanque", back_populates="cosechas")
    ola = relationship("CosechaOla", back_populates="cosechas")
    creator = relationship("Usuario", back_populates="cosechas_creadas", foreign_keys=[created_by])
    confirmador = relationship("Usuario", back_populates="cosecha_confirmadas", foreign_keys=[confirmado_por])
    cambios_fecha = relationship("CosechaFechaLog", back_populates="cosecha", cascade="all, delete-orphan")

class CosechaFechaLog(Base):
    __tablename__ = "cosecha_fecha_log"

    cosecha_fecha_log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cosecha_estanque_id = Column(BigInteger, ForeignKey("cosecha_estanque.cosecha_estanque_id"), nullable=False)
    fecha_anterior = Column(Date, nullable=False)
    fecha_nueva = Column(Date, nullable=False)
    motivo = Column(String(255))
    changed_by = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    changed_at = Column(DateTime, server_default=func.now(), nullable=False)

    cosecha = relationship("CosechaEstanque", back_populates="cambios_fecha")
    user = relationship("Usuario")
