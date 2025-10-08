from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session
from typing import Optional
from utils.db import get_db
from utils.dependencies import get_current_user
from models.usuario import Usuario
from schemas.ciclo import CicloCreate, CicloOut
from services.cycles_service import create_cycle, list_cycles, get_cycle

router = APIRouter(prefix="/farms/{granja_id}/cycles", tags=["cycles"])

@router.post("", response_model=CicloOut)
def create_cycle_endpoint(
    granja_id: int = Path(..., gt=0),
    body: CicloCreate = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    c, draft_id = create_cycle(db, user, granja_id, body)
    return {
        "ciclo_id": c.ciclo_id,
        "granja_id": c.granja_id,
        "nombre": c.nombre,
        "fecha_inicio": c.fecha_inicio,
        "fecha_fin_planificada": c.fecha_fin_planificada,
        "estado": c.estado,
        "observaciones": c.observaciones,
        "proyeccion_borrador_id": draft_id,
    }

@router.get("", response_model=list[CicloOut])
def list_cycles_endpoint(
    granja_id: int = Path(..., gt=0),
    estado: Optional[str] = Query(None, pattern="^(a|t)$"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    items = list_cycles(db, user, granja_id, estado)
    resp = []
    for c in items:
        resp.append({
            "ciclo_id": c.ciclo_id,
            "granja_id": c.granja_id,
            "nombre": c.nombre,
            "fecha_inicio": c.fecha_inicio,
            "fecha_fin_planificada": c.fecha_fin_planificada,
            "estado": c.estado,
            "observaciones": c.observaciones,
            "proyeccion_borrador_id": None,  # solo se informa en el POST
        })
    return resp

@router.get("/{ciclo_id}", response_model=CicloOut)
def get_cycle_endpoint(
    granja_id: int = Path(..., gt=0),
    ciclo_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    c = get_cycle(db, user, ciclo_id)
    # granja_id en path debe corresponder
    if c.granja_id != granja_id:
        # evitamos filtrar por ciclos de otras granjas
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cycle_not_found")
    return {
        "ciclo_id": c.ciclo_id,
        "granja_id": c.granja_id,
        "nombre": c.nombre,
        "fecha_inicio": c.fecha_inicio,
        "fecha_fin_planificada": c.fecha_fin_planificada,
        "estado": c.estado,
        "observaciones": c.observaciones,
        "proyeccion_borrador_id": None,
    }
