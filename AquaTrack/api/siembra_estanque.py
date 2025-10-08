# api/siembra_estanque.py
from typing import Optional, Dict, Any, Tuple
from fastapi import APIRouter, Depends, Query, status, Response
from sqlalchemy.orm import Session

from utils.dependencies import get_db, get_current_user
from utils.permissions import ensure_roles, ensure_visibility_granja
from enums.roles import Role
from enums.enums import SiembraEstadoEnum
from services import siembra_estanque_service
from schemas.siembra_estanque import (
    SiembraEstanqueCreate,
    SiembraEstanqueUpdate,
    SiembraEstanqueConfirm,
    SiembraEstanqueOut,
)
from models.usuario import Usuario

router = APIRouter(
    prefix="/granjas/{granja_id}/ciclos/{ciclo_id}/siembras",
    tags=["Siembras - Por Estanque"],
)

@router.get("", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def list_siembras(
    granja_id: int,
    ciclo_id: int,
    estado: Optional[SiembraEstadoEnum] = Query(None),
    estanque_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    order_by: str = Query("created_at", pattern="^(fecha_tentativa|fecha_siembra|created_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    items, total = siembra_estanque_service.list_siembras(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order=order,
        estado=estado,
        estanque_id=estanque_id,
    )
    return {
        "items": [SiembraEstanqueOut.model_validate(i) for i in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }

@router.post("", response_model=SiembraEstanqueOut, status_code=status.HTTP_201_CREATED)
def create_siembra(
    granja_id: int,
    ciclo_id: int,
    payload: SiembraEstanqueCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Permitir admin_global, admin_granja y biologo
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja, Role.biologo])
    ensure_visibility_granja(db, current_user, granja_id)
    obj = siembra_estanque_service.create_siembra(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        data=payload.model_dump(),
    )
    return SiembraEstanqueOut.model_validate(obj)

@router.get("/{siembra_estanque_id}", response_model=SiembraEstanqueOut, status_code=status.HTTP_200_OK)
def get_siembra(
    granja_id: int,
    ciclo_id: int,
    siembra_estanque_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    obj = siembra_estanque_service.get_siembra(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        siembra_estanque_id=siembra_estanque_id,
    )
    return SiembraEstanqueOut.model_validate(obj)

@router.patch("/{siembra_estanque_id}", response_model=SiembraEstanqueOut, status_code=status.HTTP_200_OK)
def update_siembra(
    granja_id: int,
    ciclo_id: int,
    siembra_estanque_id: int,
    payload: SiembraEstanqueUpdate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Permitir admin_global, admin_granja y biologo
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja, Role.biologo])
    ensure_visibility_granja(db, current_user, granja_id)
    obj, proy_id = siembra_estanque_service.update_siembra(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        siembra_estanque_id=siembra_estanque_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    if proy_id:
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return SiembraEstanqueOut.model_validate(obj)

@router.post("/{siembra_estanque_id}/confirmar", response_model=SiembraEstanqueOut, status_code=status.HTTP_200_OK)
def confirmar_siembra(
    granja_id: int,
    ciclo_id: int,
    siembra_estanque_id: int,
    payload: SiembraEstanqueConfirm,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Mantener confirmación para admin_* (si decides incluir biólogo, añádelo aquí)
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)

    obj, proy_id = siembra_estanque_service.confirm_siembra(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        siembra_estanque_id=siembra_estanque_id,
        fecha_siembra=payload.fecha_siembra,
        observaciones=payload.observaciones,
        justificacion=payload.justificacion_cambio_fecha,
    )
    if proy_id:
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return SiembraEstanqueOut.model_validate(obj)

@router.delete("/{siembra_estanque_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_siembra(
    granja_id: int,
    ciclo_id: int,
    siembra_estanque_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global])
    ensure_visibility_granja(db, current_user, granja_id)
    siembra_estanque_service.delete_siembra(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        siembra_estanque_id=siembra_estanque_id,
    )
    return None
