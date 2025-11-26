from sqlalchemy.orm import Session
from models.projection_job import ProyeccionJob
from fastapi import HTTPException


def get_job_by_id(db: Session, job_id: str) -> ProyeccionJob:
    """Obtener un job por su ID"""
    job = db.query(ProyeccionJob).filter(ProyeccionJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return job


def create_job(db: Session, job_id: str, usuario_id: int, ciclo_id: int) -> ProyeccionJob:
    """Crear un nuevo job en la BD"""
    job = ProyeccionJob(
        job_id=job_id,
        usuario_id=usuario_id,
        ciclo_id=ciclo_id,
        status="pending"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job