from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_user
from services.permissions_service import ensure_user_in_farm_or_admin
from models.usuario import Usuario
from models.estanque import Estanque
from models.granja import Granja
from schemas.estanque import EstanqueCreate, EstanqueOut

router = APIRouter(prefix="/ponds", tags=["ponds"])

@router.get("", response_model=list[EstanqueOut])
def list_ponds(
    granja_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ensure_user_in_farm_or_admin(db, user, granja_id)
    items = (
        db.query(Estanque)
        .filter(Estanque.granja_id == granja_id)
        .order_by(Estanque.nombre.asc())
        .all()
    )
    return [
        {
            "estanque_id": e.estanque_id,
            "granja_id": e.granja_id,
            "nombre": e.nombre,
            "superficie_m2": float(e.superficie_m2),
            "status": e.status,
        }
        for e in items
    ]

@router.post("", response_model=EstanqueOut)
def create_pond(
    body: EstanqueCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    # Solo admin_global o admin_granja (próximos sprints: mapear rol a scope)
    ensure_user_in_farm_or_admin(db, user, body.granja_id)
    # Valida que exista granja
    g = db.get(Granja, body.granja_id)
    if not g:
        raise HTTPException(status_code=404, detail="farm_not_found")
    e = Estanque(
        granja_id=body.granja_id,
        nombre=body.nombre,
        superficie_m2=body.superficie_m2,
        status=body.status,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return {
        "estanque_id": e.estanque_id,
        "granja_id": e.granja_id,
        "nombre": e.nombre,
        "superficie_m2": float(e.superficie_m2),
        "status": e.status,
    }
