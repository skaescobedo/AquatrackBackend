from sqlalchemy import Column, BigInteger, String, DateTime, CHAR, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class Archivo(Base):
    __tablename__ = "archivo"

    archivo_id = Column(BigInteger, primary_key=True, autoincrement=True)
    nombre_original = Column(String(200), nullable=False)
    tipo_mime = Column(String(120), nullable=False)
    tamanio_bytes = Column(BigInteger, nullable=False)
    storage_path = Column(String(300), nullable=False)
    checksum = Column(CHAR(64))
    subido_por = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    uploader = relationship("Usuario", back_populates="archivos_subidos")
    proyecciones = relationship("ArchivoProyeccion", back_populates="archivo")
    siembra_planes = relationship("ArchivoSiembraPlan", back_populates="archivo")
    plan_cosechas = relationship("ArchivoPlanCosechas", back_populates="archivo")
