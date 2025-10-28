from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import ensure_user_in_farm_or_admin
from models.user import Usuario
from models.pond import Estanque
from models.farm import Granja
from schemas.pond import PondCreate, PondOut, PondUpdate
from services.pond_service import (
    create_pond, list_ponds_by_farm, get_pond, update_pond
)

router = APIRouter(prefix="/ponds", tags=["ponds"])

@router.post("/farms/{granja_id}", response_model=PondOut, status_code=201)
def create_pond_for_farm(
    granja_id: int,
    payload: PondCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    # Solo usuarios de la granja (o admin global)
    ensure_user_in_farm_or_admin(db, user.usuario_id, granja_id, user.is_admin_global)
    return create_pond(db, granja_id, payload)

@router.get("/farms/{granja_id}", response_model=list[PondOut])
def list_farm_ponds_endpoint(
    granja_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ensure_user_in_farm_or_admin(db, user.usuario_id, granja_id, user.is_admin_global)
    return list_ponds_by_farm(db, granja_id)

@router.get("/{estanque_id}", response_model=PondOut)
def get_pond_by_id(
    estanque_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    pond = get_pond(db, estanque_id)
    # Verificar pertenencia por granja del estanque
    ensure_user_in_farm_or_admin(db, user.usuario_id, pond.granja_id, user.is_admin_global)
    return pond

@router.patch("/{estanque_id}", response_model=PondOut)
def patch_pond(
    estanque_id: int,
    payload: PondUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    # Cargar para validar permisos de granja
    pond = db.get(Estanque, estanque_id)
    if not pond:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Estanque no encontrado")
    ensure_user_in_farm_or_admin(db, user.usuario_id, pond.granja_id, user.is_admin_global)
    return update_pond(db, estanque_id, payload)
