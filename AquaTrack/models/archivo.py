from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from utils.db import Base

class Archivo(Base):
    __tablename__ = "archivo"
    archivo_id = Column(BigInteger, primary_key=True, autoincrement=True)
    nombre_original = Column(String(200), nullable=False)
    tipo_mime = Column(String(120), nullable=False)
    tamanio_bytes = Column(BigInteger, nullable=False)
    storage_path = Column(String(300), nullable=False)
    checksum = Column(String(64), unique=True)
    subido_por = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
