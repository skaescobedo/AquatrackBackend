from fastapi import APIRouter, Depends, Path, HTTPException, status
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from models.user import Usuario
from models.projection_job import ProyeccionJob
from schemas.job import JobOut
from services.job_service import get_job_by_id

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/{job_id}",
    response_model=JobOut,
    summary="Consultar estado de procesamiento de proyección",
    description=(
            "Obtiene el estado actual de un job de procesamiento de proyección.\n\n"
            "**Estados posibles:**\n"
            "- `pending`: Encolado, esperando que un worker lo procese\n"
            "- `processing`: Un worker está procesando la proyección con Gemini\n"
            "- `completed`: Completado exitosamente, proyeccion_id está disponible\n"
            "- `failed`: Error durante el procesamiento, error_detail contiene el error\n\n"
            "**Cliente debe hacer polling:** GET cada 2-3 segundos hasta que status sea 'completed' o 'failed'"
    )
)
def get_job_status(
        job_id: str = Path(..., description="ID del job a consultar"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Consultar el estado de un job.

    El usuario debe ser quien lo creó o ser admin.
    """
    job = get_job_by_id(db, job_id)

    # Validar que el usuario sea quien creó el job o sea admin
    if job.usuario_id != current_user.usuario_id and not current_user.is_admin_global:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver este job"
        )

    return job