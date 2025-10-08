from sqlalchemy import Column, BigInteger, String
from utils.db import Base

class Rol(Base):
    __tablename__ = "rol"
    rol_id = Column(BigInteger, primary_key=True, autoincrement=True)
    nombre = Column(String(80), nullable=False, unique=True)
    descripcion = Column(String(255))
