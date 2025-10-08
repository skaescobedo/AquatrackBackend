from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_user
from services.permissions_service import ensure_user_in_farm_or_admin
from models.usuario import Usuario
from models.granja import Granja
from schemas.granja import GranjaCreate, GranjaOut

router = APIRouter(prefix="/farms", tags=["farms"])

@router.get("", response_model=list[GranjaOut])
def list_farms(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    # Admin global ve todas, el resto podría ver solo vinculadas (próximos sprints).
    q = db.query(Granja)
    return [
        {
            "granja_id": g.granja_id,
            "nombre": g.nombre,
            "ubicacion": g.ubicacion,
            "descripcion": g.descripcion,
            "superficie_total_m2": float(g.superficie_total_m2),
        }
        for g in q.all()
    ]

@router.post("", response_model=GranjaOut)
def create_farm(body: GranjaCreate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    if not user.is_admin_global:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_global_required")
    g = Granja(
        nombre=body.nombre,
        ubicacion=body.ubicacion,
        descripcion=body.descripcion,
        superficie_total_m2=body.superficie_total_m2,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return {
        "granja_id": g.granja_id,
        "nombre": g.nombre,
        "ubicacion": g.ubicacion,
        "descripcion": g.descripcion,
        "superficie_total_m2": float(g.superficie_total_m2),
    }

@router.get("/{granja_id}", response_model=GranjaOut)
def get_farm(granja_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    g = db.get(Granja, granja_id)
    if not g:
        raise HTTPException(status_code=404, detail="farm_not_found")
    ensure_user_in_farm_or_admin(db, user, granja_id)
    return {
        "granja_id": g.granja_id,
        "nombre": g.nombre,
        "ubicacion": g.ubicacion,
        "descripcion": g.descripcion,
        "superficie_total_m2": float(g.superficie_total_m2),
    }
