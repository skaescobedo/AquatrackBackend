from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from utils.dependencies import get_db, get_current_user
from enums.roles import Role
from utils.permissions import ensure_roles, ensure_visibility_granja
from services import granjas_service
from schemas.granja import GranjaCreate, GranjaUpdate, GranjaOut
from models.usuario import Usuario
# en la sección de imports (arriba)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/granjas", tags=["Granjas"])

# ----- Listar -----

@router.get("", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def list_granjas(
    q: Optional[str] = Query(None, description="Búsqueda por nombre/ubicación"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    order_by: str = Query("created_at", pattern="^(nombre|created_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    items, total = granjas_service.list_granjas(
        db=db,
        user=current_user,
        q=q,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order=order,
    )
    return {
        "items": [GranjaOut.model_validate(i) for i in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }

# ----- Crear -----

@router.post("", response_model=GranjaOut, status_code=status.HTTP_201_CREATED)
def create_granja(
    payload: GranjaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Permisos: admin_global o admin_granja
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    obj = granjas_service.create_granja(db=db, user=current_user, data=payload.model_dump())
    return GranjaOut.model_validate(obj)

# ----- Detalle -----

@router.get("/{granja_id}", response_model=GranjaOut, status_code=status.HTTP_200_OK)
def get_granja(
    granja_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    obj = granjas_service.get_granja_visible(db=db, user=current_user, granja_id=granja_id)
    return GranjaOut.model_validate(obj)

# ----- Actualizar -----

@router.patch("/{granja_id}", response_model=GranjaOut, status_code=status.HTTP_200_OK)
def update_granja(
    granja_id: int,
    payload: GranjaUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Permisos: admin_global o admin_granja + visibilidad
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj = granjas_service.update_granja(
        db=db,
        user=current_user,
        granja_id=granja_id,
        changes={k: v for k, v in payload.model_dump(exclude_unset=True).items()},
    )
    return GranjaOut.model_validate(obj)

# ----- Eliminar -----

@router.delete("/{granja_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_granja(
    granja_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Permisos: solo admin_global
    ensure_roles(current_user, [Role.admin_global])
    granjas_service.delete_granja(db=db, user=current_user, granja_id=granja_id)
    return None

# ----- Asociar usuarios (declarativo) -----

class SyncUsuariosPayload(BaseModel):
    add_usuario_ids: Optional[List[int]] = []
    remove_usuario_ids: Optional[List[int]] = []

@router.post("/{granja_id}/usuarios", status_code=status.HTTP_200_OK)
def sync_usuarios_granja(
    granja_id: int,
    payload: SyncUsuariosPayload,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # admin_global o admin_granja asociado
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    result = granjas_service.sync_usuarios_granja(
        db=db,
        user=current_user,
        granja_id=granja_id,
        add_ids=payload.add_usuario_ids,
        remove_ids=payload.remove_usuario_ids,
    )
    return result
