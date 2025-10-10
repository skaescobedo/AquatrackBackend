from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session
from typing import List
from utils.db import get_db
from utils.dependencies import get_current_user
from models.usuario import Usuario
from schemas.seeding import SiembraEstanqueOut, ReprogramIn, ConfirmIn, SiembraEstanqueOverrideIn
from services.seeding_service import list_pond_seedings, reprogram_pond, confirm_pond, update_overrides

router = APIRouter(prefix="/seeding/ponds", tags=["seeding"])

@router.get("/cycles/{ciclo_id}", response_model=List[SiembraEstanqueOut])
def list_by_cycle(
    ciclo_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    items = list_pond_seedings(db, user, ciclo_id)
    return [
        {
            "siembra_estanque_id": se.siembra_estanque_id,
            "siembra_plan_id": se.siembra_plan_id,
            "estanque_id": se.estanque_id,
            "estado": se.estado,
            "fecha_tentativa": se.fecha_tentativa,
            "fecha_siembra": se.fecha_siembra,
            "lote": se.lote,
            "densidad_override_org_m2": float(se.densidad_override_org_m2) if se.densidad_override_org_m2 is not None else None,
            "talla_inicial_override_g": float(se.talla_inicial_override_g) if se.talla_inicial_override_g is not None else None,
            "observaciones": se.observaciones,
        } for se in items
    ]

@router.patch("/{siembra_estanque_id}", response_model=SiembraEstanqueOut)
def reprogram_endpoint(
    siembra_estanque_id: int = Path(..., gt=0),
    body: ReprogramIn = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    se = reprogram_pond(db, user, siembra_estanque_id, body.fecha_nueva, body.motivo)
    return {
        "siembra_estanque_id": se.siembra_estanque_id,
        "siembra_plan_id": se.siembra_plan_id,
        "estanque_id": se.estanque_id,
        "estado": se.estado,
        "fecha_tentativa": se.fecha_tentativa,
        "fecha_siembra": se.fecha_siembra,
        "lote": se.lote,
        "densidad_override_org_m2": float(se.densidad_override_org_m2) if se.densidad_override_org_m2 is not None else None,
        "talla_inicial_override_g": float(se.talla_inicial_override_g) if se.talla_inicial_override_g is not None else None,
        "observaciones": se.observaciones,
    }

@router.post("/{siembra_estanque_id}/confirm", response_model=SiembraEstanqueOut)
def confirm_endpoint(
    siembra_estanque_id: int = Path(..., gt=0),
    body: ConfirmIn = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    se = confirm_pond(db, user, siembra_estanque_id, body)
    return {
        "siembra_estanque_id": se.siembra_estanque_id,
        "siembra_plan_id": se.siembra_plan_id,
        "estanque_id": se.estanque_id,
        "estado": se.estado,
        "fecha_tentativa": se.fecha_tentativa,
        "fecha_siembra": se.fecha_siembra,
        "lote": se.lote,
        "densidad_override_org_m2": float(se.densidad_override_org_m2) if se.densidad_override_org_m2 is not None else None,
        "talla_inicial_override_g": float(se.talla_inicial_override_g) if se.talla_inicial_override_g is not None else None,
        "observaciones": se.observaciones,
    }

@router.patch("/{siembra_estanque_id}/overrides", response_model=SiembraEstanqueOut)
def overrides_endpoint(
    siembra_estanque_id: int = Path(..., gt=0),
    body: SiembraEstanqueOverrideIn = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    se = update_overrides(db, user, siembra_estanque_id, body)
    return {
        "siembra_estanque_id": se.siembra_estanque_id,
        "siembra_plan_id": se.siembra_plan_id,
        "estanque_id": se.estanque_id,
        "estado": se.estado,
        "fecha_tentativa": se.fecha_tentativa,
        "fecha_siembra": se.fecha_siembra,
        "lote": se.lote,
        "densidad_override_org_m2": float(se.densidad_override_org_m2) if se.densidad_override_org_m2 is not None else None,
        "talla_inicial_override_g": float(se.talla_inicial_override_g) if se.talla_inicial_override_g is not None else None,
        "observaciones": se.observaciones,
    }