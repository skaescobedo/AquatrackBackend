from sqlalchemy import Column, BigInteger, String, DateTime, CHAR, Boolean, ForeignKey
from sqlalchemy.sql import func
from utils.db import Base

class Proyeccion(Base):
    __tablename__ = "proyeccion"
    proyeccion_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id = Column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False, index=True)
    version = Column(String(20), nullable=False)
    descripcion = Column(String(255))
    status = Column(CHAR(1), nullable=False, default="b")
    is_current = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime)
    creada_por = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    source_type = Column(String(20))
    source_ref = Column(String(120))
    parent_version_id = Column(BigInteger, ForeignKey("proyeccion.proyeccion_id"))
    sob_final_objetivo_pct = Column(String(10))
    siembra_ventana_inicio = Column(DateTime)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
