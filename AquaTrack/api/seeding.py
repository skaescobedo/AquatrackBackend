from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import ensure_user_in_farm_or_admin
from models.user import Usuario
from models.cycle import Ciclo
from schemas.seeding import (
    SeedingPlanCreate, SeedingPlanOut, SeedingPlanDetailOut,
    SeedingPondCreate, SeedingPondOut, SeedingPondReprogram
)
from services.seeding_service import (
    create_plan_with_autofill, get_plan_detail, list_seedings_of_plan,
    create_manual_seeding_for_pond, reprogram_seeding_date
)

router = APIRouter(prefix="/seeding", tags=["seeding"])


# ---- PLAN ----
@router.post("/cycles/{ciclo_id}/plan", response_model=SeedingPlanDetailOut, status_code=status.HTTP_201_CREATED)
def post_seeding_plan(
    ciclo_id: int,
    payload: SeedingPlanCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    # Permiso: pertenencia a la granja del ciclo o admin global
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    plan = create_plan_with_autofill(db, ciclo_id, payload, current_user_id=user.usuario_id)
    siembras = list_seedings_of_plan(db, plan.siembra_plan_id)
    return {
        **SeedingPlanOut.model_validate(plan).model_dump(),
        "siembras": [SeedingPondOut.model_validate(x).model_dump() for x in siembras],
    }


@router.get("/plans/{siembra_plan_id}", response_model=SeedingPlanDetailOut)
def get_seeding_plan(siembra_plan_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    plan = get_plan_detail(db, siembra_plan_id)
    cycle = db.get(Ciclo, plan.ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)
    siembras = list_seedings_of_plan(db, siembra_plan_id)
    return {
        **SeedingPlanOut.model_validate(plan).model_dump(),
        "siembras": [SeedingPondOut.model_validate(x).model_dump() for x in siembras],
    }


# ---- SIEMBRA POR ESTANQUE (manual para faltantes) ----
@router.post("/plans/{siembra_plan_id}/ponds/{estanque_id}", response_model=SeedingPondOut, status_code=status.HTTP_201_CREATED)
def post_seeding_for_pond(
    siembra_plan_id: int,
    estanque_id: int,
    payload: SeedingPondCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    plan = get_plan_detail(db, siembra_plan_id)
    cycle = db.get(Ciclo, plan.ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    se = create_manual_seeding_for_pond(db, siembra_plan_id, estanque_id, payload, current_user_id=user.usuario_id)
    return se


@router.post("/seedings/{siembra_estanque_id}/reprogram", response_model=SeedingPondOut)
def post_reprogram_seeding(
    siembra_estanque_id: int,
    payload: SeedingPondReprogram,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    se = reprogram_seeding_date(db, siembra_estanque_id, payload.fecha_nueva, payload.motivo, current_user_id=user.usuario_id)
    # Permiso: se valida a nivel plan->ciclo->granja
    plan = get_plan_detail(db, se.siembra_plan_id)
    cycle = db.get(Ciclo, plan.ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)
    return se
