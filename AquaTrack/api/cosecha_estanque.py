# api/cosecha_estanque.py
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status, Response
from sqlalchemy.orm import Session

from utils.dependencies import get_db, get_current_user
from utils.permissions import ensure_roles, ensure_visibility_granja
from enums.roles import Role
from enums.enums import CosechaEstadoDetEnum
from services import cosecha_estanque_service
from schemas.cosecha_estanque import (
    CosechaEstanqueCreate,
    CosechaEstanqueUpdate,
    CosechaEstanqueConfirm,
    CosechaEstanqueOut,
)
from models.usuario import Usuario
from config.settings import settings

router = APIRouter(
    prefix="/granjas/{granja_id}/ciclos/{ciclo_id}/cosecha-olas/{ola_id}/cosechas",
    tags=["Cosechas - Por Estanque"],
)

@router.get("", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def list_cosechas(
    granja_id: int,
    ciclo_id: int,
    ola_id: int,
    estado: Optional[CosechaEstadoDetEnum] = Query(None),
    estanque_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    order_by: str = Query("created_at", pattern="^(fecha_cosecha|created_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    items, total = cosecha_estanque_service.list_cosechas(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        ola_id=ola_id,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order=order,
        estado=estado,
        estanque_id=estanque_id,
    )
    return {
        "items": [CosechaEstanqueOut.model_validate(i) for i in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }

@router.post("", response_model=CosechaEstanqueOut, status_code=status.HTTP_201_CREATED)
def create_cosecha(
    granja_id: int,
    ciclo_id: int,
    ola_id: int,
    payload: CosechaEstanqueCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj, proy_id = cosecha_estanque_service.create_cosecha(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        ola_id=ola_id,
        data=payload.model_dump(),
    )
    if proy_id and getattr(settings, "PROYECCION_EMIT_HEADERS", True):
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return CosechaEstanqueOut.model_validate(obj)

@router.get("/{det_id}", response_model=CosechaEstanqueOut, status_code=status.HTTP_200_OK)
def get_cosecha(
    granja_id: int,
    ciclo_id: int,
    ola_id: int,
    det_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    obj = cosecha_estanque_service.get_cosecha(
        db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, ola_id=ola_id, det_id=det_id
    )
    return CosechaEstanqueOut.model_validate(obj)

@router.patch("/{det_id}", response_model=CosechaEstanqueOut, status_code=status.HTTP_200_OK)
def update_cosecha(
    granja_id: int,
    ciclo_id: int,
    ola_id: int,
    det_id: int,
    payload: CosechaEstanqueUpdate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj, proy_id = cosecha_estanque_service.update_cosecha(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        ola_id=ola_id,
        det_id=det_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    if proy_id and getattr(settings, "PROYECCION_EMIT_HEADERS", True):
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return CosechaEstanqueOut.model_validate(obj)

@router.post("/{det_id}/confirmar", response_model=CosechaEstanqueOut, status_code=status.HTTP_200_OK)
def confirmar_cosecha(
    granja_id: int,
    ciclo_id: int,
    ola_id: int,
    det_id: int,
    payload: CosechaEstanqueConfirm,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)

    obj, proy_id = cosecha_estanque_service.confirm_cosecha(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        ola_id=ola_id,
        det_id=det_id,
        fecha_cosecha=payload.fecha_cosecha,
        pp_g=payload.pp_g,
        biomasa_kg=payload.biomasa_kg,
        densidad_retirada_org_m2=payload.densidad_retirada_org_m2,
        notas=payload.notas,
        justificacion_cambio_fecha=payload.justificacion_cambio_fecha,
    )
    if proy_id and getattr(settings, "PROYECCION_EMIT_HEADERS", True):
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return CosechaEstanqueOut.model_validate(obj)

@router.delete("/{det_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cosecha(
    granja_id: int,
    ciclo_id: int,
    ola_id: int,
    det_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global])
    ensure_visibility_granja(db, current_user, granja_id)
    proy_id = cosecha_estanque_service.delete_cosecha(
        db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, ola_id=ola_id, det_id=det_id
    )
    if proy_id and getattr(settings, "PROYECCION_EMIT_HEADERS", True):
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return None
