from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import ensure_user_in_farm_or_admin

from models.user import Usuario
from models.cycle import Ciclo
from models.seeding import SiembraPlan, SiembraEstanque

from schemas.seeding import (
    SeedingPlanCreate, SeedingPlanOut, SeedingPlanWithItemsOut,
    SeedingCreateForPond, SeedingOut, SeedingReprogramIn, SeedingFechaLogOut
)
from services.seeding_service import (
    create_plan_and_autoseed,
    get_plan_with_items_by_cycle,
    create_manual_seeding_for_pond,
    reprogram_seeding,
    confirm_seeding,
    delete_plan_if_no_confirmed
)

router = APIRouter(prefix="/seeding", tags=["seeding"])


# ------------------------
# POST plan (auto-crear siembras distribuidas)
# ------------------------
@router.post("/cycles/{ciclo_id}/plan", response_model=SeedingPlanOut, status_code=201)
def post_seeding_plan(
    ciclo_id: int,
    payload: SeedingPlanCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    plan = create_plan_and_autoseed(db, ciclo_id, payload, created_by_user_id=user.usuario_id)
    return plan


# ------------------------
# GET plan + siembras
# ------------------------
@router.get("/cycles/{ciclo_id}/plan", response_model=SeedingPlanWithItemsOut)
def get_seeding_plan(
    ciclo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    plan = get_plan_with_items_by_cycle(db, ciclo_id)
    return {
        **SeedingPlanOut.model_validate(plan, from_attributes=True).model_dump(),
        "siembras": [SeedingOut.model_validate(s, from_attributes=True).model_dump() for s in plan.siembras],
    }


# ------------------------
# POST siembra manual para un estanque que falta
# ------------------------
@router.post("/plan/{siembra_plan_id}/ponds/{estanque_id}", response_model=SeedingOut, status_code=201)
def post_seeding_for_pond(
    siembra_plan_id: int,
    estanque_id: int,
    payload: SeedingCreateForPond,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    plan = db.get(SiembraPlan, siembra_plan_id)
    if not plan:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Plan de siembras no encontrado")

    cycle = db.get(Ciclo, plan.ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    seeding = create_manual_seeding_for_pond(
        db, siembra_plan_id, estanque_id, payload, created_by_user_id=user.usuario_id
    )
    return seeding


# ------------------------
# POST reprogramar siembra (fecha/densidad/talla/lote)
# ------------------------
@router.post(
    "/seedings/{siembra_estanque_id}/reprogram",
    response_model=SeedingOut,
    description=(
        "Semántica del payload:\n\n"
        "- **`null`** en cualquier campo ⇒ **NO cambia** ese valor.\n"
        "- **`0`** en `densidad_override_org_m2` o `talla_inicial_override_g` ⇒ **NO cambia**.\n"
        "- **Cualquier valor válido distinto de 0** ⇒ **ACTUALIZA**.\n"
        "- Para `lote` (string): `null` ⇒ no cambia; cadena (incluida `\"\"`) ⇒ se asigna/limpia.\n"
    ),
    openapi_extra={
        "examples": {
            "no_cambia_nada": {
                "summary": "No cambiar nada (todo null)",
                "value": {"fecha_nueva": None, "lote": None, "densidad_override_org_m2": None, "talla_inicial_override_g": None, "motivo": None}
            },
            "solo_fecha": {
                "summary": "Solo cambiar fecha",
                "value": {"fecha_nueva": "2025-10-28", "lote": None, "densidad_override_org_m2": None, "talla_inicial_override_g": None, "motivo": "ajuste agenda"}
            },
            "densidad_y_talla_ignorar_por_cero": {
                "summary": "Cero no cambia overrides",
                "value": {"fecha_nueva": None, "lote": None, "densidad_override_org_m2": 0, "talla_inicial_override_g": 0, "motivo": None}
            },
            "limpiar_lote": {
                "summary": "Limpiar el lote (cadena vacía)",
                "value": {"fecha_nueva": None, "lote": "", "densidad_override_org_m2": None, "talla_inicial_override_g": None, "motivo": "sin lote definido"}
            },
            "actualizar_todo": {
                "summary": "Actualizar todo",
                "value": {"fecha_nueva": "2025-11-02", "lote": "L-2025A", "densidad_override_org_m2": 10.25, "talla_inicial_override_g": 1.8, "motivo": "replaneación"}
            },
        }
    }
)
def post_reprogram_seeding(
    siembra_estanque_id: int,
    payload: SeedingReprogramIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    seeding = db.get(SiembraEstanque, siembra_estanque_id)
    if not seeding:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Siembra no encontrada")

    plan = db.get(SiembraPlan, seeding.siembra_plan_id)
    cycle = db.get(Ciclo, plan.ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    updated = reprogram_seeding(db, siembra_estanque_id, payload, changed_by_user_id=user.usuario_id)
    return updated


# ------------------------
# POST confirmar siembra (status=f, fecha_siembra=hoy; activa estanque)
# ------------------------
@router.post("/seedings/{siembra_estanque_id}/confirm", response_model=SeedingOut)
def post_confirm_seeding(
    siembra_estanque_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    seeding = db.get(SiembraEstanque, siembra_estanque_id)
    if not seeding:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Siembra no encontrada")

    plan = db.get(SiembraPlan, seeding.siembra_plan_id)
    cycle = db.get(Ciclo, plan.ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    updated = confirm_seeding(db, siembra_estanque_id, confirmed_by_user_id=user.usuario_id)
    return updated


# ------------------------
# DELETE plan (solo si no hay confirmadas)
# ------------------------
@router.delete("/plan/{siembra_plan_id}", status_code=204)
def delete_seeding_plan(
    siembra_plan_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    plan = db.get(SiembraPlan, siembra_plan_id)
    if not plan:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Plan de siembras no encontrado")

    cycle = db.get(Ciclo, plan.ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    delete_plan_if_no_confirmed(db, siembra_plan_id)
