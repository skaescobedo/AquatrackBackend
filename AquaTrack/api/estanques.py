from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from utils.dependencies import get_db, get_current_user
from enums.enums import  EstanqueStatusEnum
from enums.roles import  Role
from utils.permissions import ensure_roles, ensure_visibility_granja
from services import estanques_service
from schemas.estanque import EstanqueCreate, EstanqueUpdate, EstanqueOut
from models.usuario import Usuario

router = APIRouter(prefix="/granjas/{granja_id}/estanques", tags=["Estanques"])

# ------- Listar -------

@router.get("", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def list_estanques(
    granja_id: int,
    q: Optional[str] = Query(None, description="Búsqueda por nombre"),
    status_filter: Optional[EstanqueStatusEnum] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    order_by: str = Query("created_at", pattern="^(nombre|superficie_m2|created_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    items, total = estanques_service.list_estanques(
        db=db,
        user=current_user,
        granja_id=granja_id,
        q=q,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order=order,
    )
    return {
        "items": [EstanqueOut.model_validate(i) for i in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }

# ------- Crear -------

@router.post("", response_model=EstanqueOut, status_code=status.HTTP_201_CREATED)
def create_estanque(
    granja_id: int,
    payload: EstanqueCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj = estanques_service.create_estanque(db=db, user=current_user, granja_id=granja_id, data=payload.model_dump())
    return EstanqueOut.model_validate(obj)

# ------- Detalle -------

@router.get("/{estanque_id}", response_model=EstanqueOut, status_code=status.HTTP_200_OK)
def get_estanque(
    granja_id: int,
    estanque_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    obj = estanques_service.get_estanque_visible(db=db, user=current_user, granja_id=granja_id, estanque_id=estanque_id)
    return EstanqueOut.model_validate(obj)

# ------- Actualizar -------

@router.patch("/{estanque_id}", response_model=EstanqueOut, status_code=status.HTTP_200_OK)
def update_estanque(
    granja_id: int,
    estanque_id: int,
    payload: EstanqueUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj = estanques_service.update_estanque(
        db=db,
        user=current_user,
        granja_id=granja_id,
        estanque_id=estanque_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    return EstanqueOut.model_validate(obj)

# ------- Eliminar -------

@router.delete("/{estanque_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_estanque(
    granja_id: int,
    estanque_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global])
    ensure_visibility_granja(db, current_user, granja_id)
    estanques_service.delete_estanque(db=db, user=current_user, granja_id=granja_id, estanque_id=estanque_id)
    return None
