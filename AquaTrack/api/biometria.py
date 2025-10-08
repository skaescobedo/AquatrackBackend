# api/biometria.py
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status, Response
from sqlalchemy.orm import Session

from utils.dependencies import get_db, get_current_user
from utils.permissions import ensure_roles, ensure_visibility_granja
from enums.roles import Role
from models.usuario import Usuario
from schemas.biometria import BiometriaCreate, BiometriaOut
from services import biometria_service

router = APIRouter(
    prefix="/granjas/{granja_id}/ciclos/{ciclo_id}/biometrias",
    tags=["Biometrías"],
)

@router.get("", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def list_biometrias(
    granja_id: int,
    ciclo_id: int,
    estanque_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    order_by: str = Query("fecha", pattern="^(fecha|created_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    items, total = biometria_service.list_biometrias(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        estanque_id=estanque_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order=order,
    )
    return {
        "items": [BiometriaOut.model_validate(i) for i in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }

@router.get("/{biometria_id}", response_model=BiometriaOut, status_code=status.HTTP_200_OK)
def get_biometria(
    granja_id: int,
    ciclo_id: int,
    biometria_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    obj = biometria_service.get_biometria(
        db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, biometria_id=biometria_id
    )
    return BiometriaOut.model_validate(obj)

@router.post("", response_model=BiometriaOut, status_code=status.HTTP_201_CREATED)
def create_biometria(
    granja_id: int,
    ciclo_id: int,
    payload: BiometriaCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Permisos: admin_* y biólogo pueden capturar biometrías
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja, Role.biologo])
    ensure_visibility_granja(db, current_user, granja_id)

    obj = biometria_service.create_biometria(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        data=payload.model_dump(),
    )
    return BiometriaOut.model_validate(obj)

@router.delete("/{biometria_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_biometria(
    granja_id: int,
    ciclo_id: int,
    biometria_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Mantén eliminación sólo para admin_global (alineado con tus otros delete)
    ensure_roles(current_user, [Role.admin_global])
    ensure_visibility_granja(db, current_user, granja_id)

    biometria_service.delete_biometria(
        db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, biometria_id=biometria_id
    )
    return None
