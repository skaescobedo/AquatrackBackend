import asyncio
from datetime import datetime
from workers.celery_config import app
from sqlalchemy.orm import Session
from utils.db import SessionLocal
from models.projection_job import ProyeccionJob
from services import projection_service
from fastapi import UploadFile
import io


@app.task(bind=True, max_retries=2)
def process_projection_file_task(self, job_id: str, ciclo_id: int, file_contents: bytes, file_name: str, user_id: int):
    """Procesa archivo en memoria."""
    db = SessionLocal()

    try:
        job = db.query(ProyeccionJob).filter(ProyeccionJob.job_id == job_id).first()
        job.status = "processing"
        db.commit()

        # Crear UploadFile real
        file_obj = UploadFile(
            file=io.BytesIO(file_contents),
            size=len(file_contents),
            filename=file_name,
            headers={"content-type": "application/octet-stream"}
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        proyeccion, warnings = loop.run_until_complete(
            projection_service.create_projection_from_file(
                db=db,
                ciclo_id=ciclo_id,
                file=file_obj,
                user_id=user_id,
                descripcion=None,
                version=None,
            )
        )

        job.status = "completed"
        job.proyeccion_id = proyeccion.proyeccion_id
        job.warnings = warnings
        job.completed_at = datetime.utcnow()
        db.commit()
        db.close()

        return {"status": "completed"}

    except Exception as exc:
        db.rollback()
        job = db.query(ProyeccionJob).filter(ProyeccionJob.job_id == job_id).first()
        if job:
            job.status = "failed"
            job.error_detail = str(exc)[:500]
            job.completed_at = datetime.utcnow()
            db.commit()
        db.close()
        raise self.retry(exc=exc, countdown=5)