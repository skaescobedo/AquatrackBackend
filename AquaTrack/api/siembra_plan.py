from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_user
from models.usuario import Usuario
from schemas.seeding import SiembraPlanUpsert, SiembraPlanOut
from services.seeding_service import get_plan, upsert_plan, generate_pond_plans

router = APIRouter(prefix="/cycles/{ciclo_id}/seeding/plan", tags=["seeding"])

@router.get("", response_model=SiembraPlanOut | None)
def get_plan_endpoint(
    ciclo_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    sp = get_plan(db, user, ciclo_id)
    if not sp:
        return None
    return {
        "siembra_plan_id": sp.siembra_plan_id,
        "ciclo_id": sp.ciclo_id,
        "ventana_inicio": sp.ventana_inicio,
        "ventana_fin": sp.ventana_fin,
        "densidad_org_m2": float(sp.densidad_org_m2),
        "talla_inicial_g": float(sp.talla_inicial_g),
        "observaciones": sp.observaciones,
    }

@router.post("", response_model=SiembraPlanOut)
def upsert_plan_endpoint(
    ciclo_id: int = Path(..., gt=0),
    body: SiembraPlanUpsert = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    sp = upsert_plan(db, user, ciclo_id, body)
    return {
        "siembra_plan_id": sp.siembra_plan_id,
        "ciclo_id": sp.ciclo_id,
        "ventana_inicio": sp.ventana_inicio,
        "ventana_fin": sp.ventana_fin,
        "densidad_org_m2": float(sp.densidad_org_m2),
        "talla_inicial_g": float(sp.talla_inicial_g),
        "observaciones": sp.observaciones,
    }

@router.post("/generate")
def generate_endpoint(
    ciclo_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    # Busca plan y genera siembras para todos los estanques de la granja, distribuyendo fechas en la ventana
    sp = get_plan(db, user, ciclo_id)
    if not sp:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="seeding_plan_not_found")
    created = generate_pond_plans(db, user, sp.siembra_plan_id)
    return {"created": created}
