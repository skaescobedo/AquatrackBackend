from typing import Optional, Dict, Any
from datetime import date

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from utils.dependencies import get_db, get_current_user
from utils.permissions import ensure_roles, ensure_visibility_granja
from enums.roles import Role
from enums.enums import CicloEstadoEnum
from services import ciclos_service
from schemas.ciclo import CicloCreate, CicloUpdate, CicloOut
from models.usuario import Usuario

router = APIRouter(prefix="/granjas/{granja_id}/ciclos", tags=["Ciclos"])

# -------- Listar --------

@router.get("", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def list_ciclos(
    granja_id: int,
    q: Optional[str] = Query(None, description="Búsqueda por nombre"),
    estado: Optional[CicloEstadoEnum] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    order_by: str = Query("created_at", pattern="^(nombre|fecha_inicio|created_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    items, total = ciclos_service.list_ciclos(
        db=db,
        user=current_user,
        granja_id=granja_id,
        q=q,
        estado=estado,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order=order,
    )
    return {
        "items": [CicloOut.model_validate(i) for i in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }

# -------- Crear --------
# Nota: tu CicloCreate exige granja_id; aceptamos el body tal cual,
# pero el backend SIEMPRE usa el granja_id del path y levanta 409 si no coincide.

@router.post("", response_model=CicloOut, status_code=status.HTTP_201_CREATED)
def create_ciclo(
    granja_id: int,
    payload: CicloCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj = ciclos_service.create_ciclo(
        db=db,
        user=current_user,
        granja_id=granja_id,
        data=payload.model_dump(),
    )
    return CicloOut.model_validate(obj)

# -------- Detalle --------

@router.get("/activo", response_model=CicloOut, status_code=status.HTTP_200_OK)
def get_ciclo_activo(
    granja_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    obj = ciclos_service.get_ciclo_activo_or_404(db=db, user=current_user, granja_id=granja_id)
    return CicloOut.model_validate(obj)

@router.get("/{ciclo_id}", response_model=CicloOut, status_code=status.HTTP_200_OK)
def get_ciclo(
    granja_id: int,
    ciclo_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    obj = ciclos_service.get_ciclo_visible(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id)
    return CicloOut.model_validate(obj)

# -------- Actualizar --------

@router.patch("/{ciclo_id}", response_model=CicloOut, status_code=status.HTTP_200_OK)
def update_ciclo(
    granja_id: int,
    ciclo_id: int,
    payload: CicloUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj = ciclos_service.update_ciclo(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    return CicloOut.model_validate(obj)

# -------- Cerrar ciclo (atajo explícito) --------

class ClosePayload(BaseModel):
    fecha_cierre_real: Optional[date] = Field(None, description="Si no se envía, se usa la fecha actual.")

@router.post("/{ciclo_id}/cerrar", response_model=CicloOut, status_code=status.HTTP_200_OK)
def close_ciclo(
    granja_id: int,
    ciclo_id: int,
    payload: ClosePayload,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj = ciclos_service.close_ciclo(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        fecha_cierre_real=payload.fecha_cierre_real,
    )
    return CicloOut.model_validate(obj)

# -------- Eliminar --------

@router.delete("/{ciclo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ciclo(
    granja_id: int,
    ciclo_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global])
    ensure_visibility_granja(db, current_user, granja_id)
    ciclos_service.delete_ciclo(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id)
    return None
