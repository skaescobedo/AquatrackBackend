from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import ensure_user_in_farm_or_admin
from schemas.cycle import CycleCreate, CycleUpdate, CycleOut, CycleClose, CycleResumenOut
from services.cycle_service import (
    create_cycle, get_active_cycle, list_cycles, get_cycle, update_cycle, close_cycle
)
from models.user import Usuario
from models.cycle import Ciclo

router = APIRouter(prefix="/cycles", tags=["cycles"])


@router.post("/farms/{granja_id}", response_model=CycleOut, status_code=201)
def post_cycle(
        granja_id: int,
        payload: CycleCreate,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
):
    ensure_user_in_farm_or_admin(db, user.usuario_id, granja_id, user.is_admin_global)
    return create_cycle(db, granja_id, payload)


@router.get("/farms/{granja_id}/active", response_model=CycleOut | None)
def get_farm_active_cycle(
        granja_id: int,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
):
    ensure_user_in_farm_or_admin(db, user.usuario_id, granja_id, user.is_admin_global)
    return get_active_cycle(db, granja_id)


@router.get("/farms/{granja_id}", response_model=list[CycleOut])
def list_farm_cycles(
        granja_id: int,
        include_terminated: bool = Query(False),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
):
    ensure_user_in_farm_or_admin(db, user.usuario_id, granja_id, user.is_admin_global)
    return list_cycles(db, granja_id, include_terminated)


@router.get("/{ciclo_id}", response_model=CycleOut)
def get_cycle_by_id(
        ciclo_id: int,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
):
    cycle = get_cycle(db, ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)
    return cycle


@router.patch("/{ciclo_id}", response_model=CycleOut)
def patch_cycle(
        ciclo_id: int,
        payload: CycleUpdate,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
):
    cycle = get_cycle(db, ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)
    return update_cycle(db, ciclo_id, payload)


@router.post("/{ciclo_id}/close", response_model=CycleOut)
def post_close_cycle(
        ciclo_id: int,
        payload: CycleClose,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
):
    cycle = get_cycle(db, ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    # TODO: Calcular sob_final, toneladas, n_estanques desde calculation_service
    # Por ahora valores mock
    return close_cycle(db, ciclo_id, payload, sob_final=85.5, toneladas=12.5, n_estanques=3)


@router.get("/{ciclo_id}/resumen", response_model=CycleResumenOut)
def get_cycle_summary(
        ciclo_id: int,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
):
    cycle = get_cycle(db, ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    if not cycle.resumen:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="El ciclo no tiene resumen (aún no se ha cerrado)")

    return cycle.resumen