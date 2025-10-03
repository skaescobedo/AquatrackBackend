from sqlalchemy import Column, BigInteger, CHAR, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class UsuarioGranja(Base):
    __tablename__ = "usuario_granja"

    usuario_granja_id = Column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    granja_id = Column(BigInteger, ForeignKey("granja.granja_id"), nullable=False)
    estado = Column(CHAR(1), nullable=False, default="a")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    usuario = relationship("Usuario", back_populates="granjas")
    granja = relationship("Granja", back_populates="usuarios")

class UsuarioRol(Base):
    __tablename__ = "usuario_rol"

    usuario_id = Column(BigInteger, ForeignKey("usuario.usuario_id"), primary_key=True)
    rol_id = Column(BigInteger, ForeignKey("rol.rol_id"), primary_key=True)

    usuario = relationship("Usuario", back_populates="roles")
    rol = relationship("Rol", back_populates="usuarios")
