from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from utils.db import get_db
from schemas.pond import PondCreate, PondOut, PondUpdate
from services.pond_service import (
    create_pond, list_ponds_by_farm, get_pond, update_pond
)

router = APIRouter(prefix="/ponds", tags=["ponds"])

# Nota de permisos:
# - En producción, añade Depends(get_current_user) y verificación de usuario_granja.
# - Dejamos el esqueleto mínimo aquí.

@router.post("/farms/{granja_id}", response_model=PondOut, status_code=201)
def create_pond_for_farm(granja_id: int, payload: PondCreate, db: Session = Depends(get_db)):
    return create_pond(db, granja_id, payload)

@router.get("/farms/{granja_id}", response_model=list[PondOut])
def list_farm_ponds(granja_id: int, db: Session = Depends(get_db)):
    return list_ponds_by_farm(db, granja_id)

@router.get("/{estanque_id}", response_model=PondOut)
def get_pond_by_id(estanque_id: int, db: Session = Depends(get_db)):
    return get_pond(db, estanque_id)

@router.patch("/{estanque_id}", response_model=PondOut)
def patch_pond(estanque_id: int, payload: PondUpdate, db: Session = Depends(get_db)):
    return update_pond(db, estanque_id, payload)
