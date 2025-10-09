from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session
from typing import List
from utils.db import get_db
from utils.dependencies import get_current_user
from models.usuario import Usuario
from schemas.harvest import CosechaEstanqueOut, CosechaReprogramIn, CosechaConfirmIn
from services.harvest_service import list_harvests_by_cycle, reprogram_harvest, confirm_harvest

router = APIRouter(prefix="/harvest/ponds", tags=["harvest"])

@router.patch("/{cosecha_estanque_id}", response_model=CosechaEstanqueOut)
def reprogram_endpoint(
    cosecha_estanque_id: int = Path(..., gt=0),
    body: CosechaReprogramIn = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ce = reprogram_harvest(db, user, cosecha_estanque_id, body.fecha_nueva, body.motivo)
    return {
        "cosecha_estanque_id": ce.cosecha_estanque_id,
        "cosecha_ola_id": ce.cosecha_ola_id,
        "estanque_id": ce.estanque_id,
        "estado": ce.estado,
        "fecha_cosecha": ce.fecha_cosecha,
        "pp_g": float(ce.pp_g) if ce.pp_g is not None else None,
        "biomasa_kg": float(ce.biomasa_kg) if ce.biomasa_kg is not None else None,
        "densidad_retirada_org_m2": float(ce.densidad_retirada_org_m2) if ce.densidad_retirada_org_m2 is not None else None,
        "notas": ce.notas,
    }

@router.post("/{cosecha_estanque_id}/confirm", response_model=CosechaEstanqueOut)
def confirm_endpoint(
    cosecha_estanque_id: int = Path(..., gt=0),
    body: CosechaConfirmIn = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ce = confirm_harvest(db, user, cosecha_estanque_id, body)
    return {
        "cosecha_estanque_id": ce.cosecha_estanque_id,
        "cosecha_ola_id": ce.cosecha_ola_id,
        "estanque_id": ce.estanque_id,
        "estado": ce.estado,
        "fecha_cosecha": ce.fecha_cosecha,
        "pp_g": float(ce.pp_g) if ce.pp_g is not None else None,
        "biomasa_kg": float(ce.biomasa_kg) if ce.biomasa_kg is not None else None,
        "densidad_retirada_org_m2": float(ce.densidad_retirada_org_m2) if ce.densidad_retirada_org_m2 is not None else None,
        "notas": ce.notas,
    }
