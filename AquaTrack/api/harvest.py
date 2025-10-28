# api/harvest.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import ensure_user_in_farm_or_admin

from models.user import Usuario
from models.cycle import Ciclo

from schemas.harvest import HarvestWaveCreate, HarvestWaveOut, HarvestWaveWithItemsOut, HarvestEstanqueOut
from services.harvest_service import create_wave_and_autolines

router = APIRouter(prefix="/harvest", tags=["harvest"])

@router.post("/cycles/{ciclo_id}/wave", response_model=HarvestWaveOut, status_code=status.HTTP_201_CREATED)
def post_harvest_wave(
    ciclo_id: int = Path(..., gt=0),
    payload: HarvestWaveCreate = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    ola = create_wave_and_autolines(db, ciclo_id, payload, created_by_user_id=user.usuario_id)
    return ola
