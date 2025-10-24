from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_user
from models.usuario import Usuario
from services.reporting_service import operational_state
from schemas.reports import OperationalStateOut

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/cycles/{ciclo_id}/operational-state", response_model=OperationalStateOut)
def get_operational_state(
    ciclo_id: int = Path(..., gt=0),
    tz: str | None = Query(None, description="Zona horaria IANA, ej. America/Mazatlan"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return operational_state(db, user, ciclo_id, tz_name=tz)
