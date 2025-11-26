from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from utils.db import Base

class ProyeccionJob(Base):
    """
    Tabla para rastrear el estado de procesos de proyección asíncrona.

    Estados:
    - pending: Job encolado pero no procesado
    - processing: Worker está procesando
    - completed: Completado exitosamente
    - failed: Error durante el procesamiento
    """

    __tablename__ = "proyeccion_jobs"

    job_id = Column(String(50), primary_key=True)
    usuario_id = Column(Integer, nullable=False)
    ciclo_id = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    proyeccion_id = Column(Integer, nullable=True)
    error_detail = Column(String(500), nullable=True)
    warnings = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<ProyeccionJob {self.job_id} status={self.status}>"