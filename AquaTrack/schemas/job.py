from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class JobCreate(BaseModel):
    """Respuesta cuando se crea un job (POST /from-file)"""
    job_id: str
    status: str  # "pending"
    message: str


class JobOut(BaseModel):
    """Respuesta al consultar estado del job (GET /jobs/{job_id})"""
    job_id: str
    usuario_id: int
    ciclo_id: int
    status: str  # pending, processing, completed, failed
    proyeccion_id: Optional[int] = None
    error_detail: Optional[str] = None
    warnings: Optional[List[str]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True