from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from utils.db import Base

class ArchivoProyeccion(Base):
    __tablename__ = "archivo_proyeccion"
    archivo_proyeccion_id = Column(BigInteger, primary_key=True, autoincrement=True)
    archivo_id = Column(BigInteger, ForeignKey("archivo.archivo_id"), nullable=False, index=True)
    proyeccion_id = Column(BigInteger, ForeignKey("proyeccion.proyeccion_id"), nullable=False, index=True)
    proposito = Column(String(20), nullable=False, default="otro")  # mapea a enum BD
    notas = Column(String(255))
    linked_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
