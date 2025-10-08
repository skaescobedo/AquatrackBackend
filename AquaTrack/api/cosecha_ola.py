# api/cosecha_ola.py
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status, Response
from sqlalchemy.orm import Session

from utils.dependencies import get_db, get_current_user
from utils.permissions import ensure_roles, ensure_visibility_granja
from enums.roles import Role
from enums.enums import CosechaEstadoEnum
from services import cosecha_ola_service
from schemas.cosecha_ola import CosechaOlaCreate, CosechaOlaUpdate, CosechaOlaOut
from models.usuario import Usuario
from config.settings import settings

router = APIRouter(
    prefix="/granjas/{granja_id}/ciclos/{ciclo_id}/cosecha-olas",
    tags=["Cosechas - Olas"],
)

@router.get("", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def list_olas(
    granja_id: int,
    ciclo_id: int,
    estado: Optional[CosechaEstadoEnum] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    order_by: str = Query("created_at", pattern="^(created_at|ventana_inicio|ventana_fin|orden)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    items, total = cosecha_ola_service.list_olas(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order=order,
        estado=estado,
    )
    return {
        "items": [CosechaOlaOut.model_validate(i) for i in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }

@router.post("", response_model=CosechaOlaOut, status_code=status.HTTP_201_CREATED)
def create_ola(granja_id: int, ciclo_id: int, payload: CosechaOlaCreate, response: Response, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj, proy_id = cosecha_ola_service.create_ola(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, data=payload.model_dump())
    if proy_id and getattr(settings, "PROYECCION_EMIT_HEADERS", True):
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return CosechaOlaOut.model_validate(obj)

@router.get("/{ola_id}", response_model=CosechaOlaOut, status_code=status.HTTP_200_OK)
def get_ola(granja_id: int, ciclo_id: int, ola_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    obj = cosecha_ola_service.get_ola(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, ola_id=ola_id)
    return CosechaOlaOut.model_validate(obj)

@router.patch("/{ola_id}", response_model=CosechaOlaOut, status_code=status.HTTP_200_OK)
def update_ola(granja_id: int, ciclo_id: int, ola_id: int, payload: CosechaOlaUpdate, response: Response, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj, proy_id = cosecha_ola_service.update_ola(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, ola_id=ola_id, changes=payload.model_dump(exclude_unset=True))
    if proy_id and getattr(settings, "PROYECCION_EMIT_HEADERS", True):
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return CosechaOlaOut.model_validate(obj)

@router.delete("/{ola_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ola(granja_id: int, ciclo_id: int, ola_id: int, response: Response, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    ensure_roles(current_user, [Role.admin_global])
    ensure_visibility_granja(db, current_user, granja_id)
    proy_id = cosecha_ola_service.delete_ola(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, ola_id=ola_id)
    if proy_id and getattr(settings, "PROYECCION_EMIT_HEADERS", True):
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return None

# ---- NUEVO: SYNC para auto-crear detalles faltantes por ola ----
@router.post("/{ola_id}/sync", response_model=dict, status_code=status.HTTP_200_OK)
def sync_cosechas_faltantes(granja_id: int, ciclo_id: int, ola_id: int, response: Response, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    created, proy_id = cosecha_ola_service.sync_cosechas_faltantes(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, ola_id=ola_id)
    if proy_id and getattr(settings, "PROYECCION_EMIT_HEADERS", True):
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return {"created": created}
