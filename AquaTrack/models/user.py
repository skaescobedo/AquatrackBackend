from sqlalchemy import Column, BigInteger, String, DateTime, CHAR
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class Usuario(Base):
    __tablename__ = "usuario"

    usuario_id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(20), nullable=False, unique=True)
    nombre = Column(String(30), nullable=False)
    apellido1 = Column(String(30), nullable=False)
    apellido2 = Column(String(30), nullable=False)
    email = Column(String(80), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    estado = Column(CHAR(1), nullable=False, default="a")  # a/i
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relaciones
    granjas = relationship("UsuarioGranja", back_populates="usuario", cascade="all, delete-orphan")
    roles = relationship("UsuarioRol", back_populates="usuario", cascade="all, delete-orphan")
    archivos_subidos = relationship("Archivo", back_populates="uploader")
    biometria_creadas = relationship("Biometria", back_populates="creator")
    siembras_creadas = relationship("SiembraEstanque", back_populates="creator")
    siembra_plan_creados = relationship("SiembraPlan", back_populates="creator")
    cosecha_olas_creadas = relationship("CosechaOla", back_populates="creator")
    cosechas_creadas = relationship("CosechaEstanque", back_populates="creator", foreign_keys="CosechaEstanque.created_by")
    cosecha_confirmadas = relationship("CosechaEstanque", back_populates="confirmador", foreign_keys="CosechaEstanque.confirmado_por")
    pcv_actualizados = relationship("ParametroCicloVersion", back_populates="updater")
    sob_cambios = relationship("SOBCambioLog", back_populates="user")
    pass_resets = relationship("PasswordResetToken", back_populates="usuario")
    proyecciones_creadas = relationship("Proyeccion", back_populates="creador")
