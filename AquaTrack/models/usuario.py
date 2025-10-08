from sqlalchemy import Column, BigInteger, String, CHAR, DateTime, Text, Boolean
from sqlalchemy.sql import func
from utils.db import Base

class Usuario(Base):
    __tablename__ = "usuario"
    usuario_id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(20), nullable=False, unique=True)
    nombre = Column(String(30), nullable=False)
    apellido1 = Column(String(30), nullable=False)
    apellido2 = Column(String(30))
    email = Column(String(80), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    estado = Column(CHAR(1), nullable=False, default="a")
    is_admin_global = Column(Boolean, nullable=False, default=False)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
