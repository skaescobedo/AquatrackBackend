from sqlalchemy import Column, BigInteger, String, Text, Date, DateTime, DECIMAL, CHAR, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.db import Base

class Tarea(Base):
    __tablename__ = "tarea"

    tarea_id = Column(BigInteger, primary_key=True, autoincrement=True)
    titulo = Column(String(160), nullable=False)
    descripcion = Column(Text)
    prioridad = Column(CHAR(1), nullable=False, default="m")  # b/m/a
    fecha_limite = Column(Date)
    tiempo_estimado_horas = Column(DECIMAL(6,2))
    estado = Column(CHAR(1), nullable=False, default="p")     # p/e/c/x
    tipo = Column(String(80))
    periodo_clave = Column(String(40))
    es_recurrente = Column(CHAR(1), nullable=False, default='0')  # tinyint(1)
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # opcional: quién creó la tarea
    creador = relationship("Usuario")
