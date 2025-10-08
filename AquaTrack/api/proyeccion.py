# api/proyeccion.py
from __future__ import annotations
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Query, status, Response, Body
from sqlalchemy.orm import Session

from utils.dependencies import get_db, get_current_user
from utils.permissions import ensure_roles, ensure_visibility_granja
from enums.roles import Role
from enums.enums import ProyeccionStatusEnum
from services import proyeccion_service
from models.usuario import Usuario

# Schemas (asumimos que ya existen en tu proyecto)
from schemas.proyeccion import ProyeccionOut
from schemas.proyeccion_linea import ProyeccionLineaOut

router = APIRouter(
    prefix="/granjas/{granja_id}/ciclos/{ciclo_id}/proyecciones",
    tags=["Proyecciones"],
)

# ---------------- Listar / Obtener ----------------

@router.get("", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def list_proyecciones(
    granja_id: int,
    ciclo_id: int,
    status_eq: Optional[ProyeccionStatusEnum] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    order_by: str = Query("created_at", pattern="^(created_at|updated_at|version|is_current|published_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    items, total = proyeccion_service.list_proyecciones(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order=order,
        status=status_eq,
    )
    return {
        "items": [ProyeccionOut.model_validate(i) for i in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/{proyeccion_id}", response_model=ProyeccionOut, status_code=status.HTTP_200_OK)
def get_proyeccion(
    granja_id: int,
    ciclo_id: int,
    proyeccion_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    obj = proyeccion_service.get_proyeccion(
        db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, proyeccion_id=proyeccion_id
    )
    return ProyeccionOut.model_validate(obj)


# ---------------- Factories (solo creación por factories) ----------------

@router.post("/bootstrap-from-plan", response_model=ProyeccionOut, status_code=status.HTTP_201_CREATED)
def bootstrap_from_plan(
    granja_id: int,
    ciclo_id: int,
    payload: Dict[str, Any] = Body(default={}),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Crea una proyección en estado 'borrador' a partir del SiembraPlan del ciclo.
    Body opcional:
      {
        "version": "v1.0",
        "descripcion": "Texto",
        "sob_final_objetivo_pct": 85.0,
        "incremento_semanal_g": 1.0,
        "sob_base_pct": 90.0
      }
    """
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)

    obj = proyeccion_service.bootstrap_from_plan(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        version=payload.get("version"),
        descripcion=payload.get("descripcion"),
        sob_final_objetivo_pct=payload.get("sob_final_objetivo_pct"),
        incremento_semanal_g=payload.get("incremento_semanal_g"),
        sob_base_pct=payload.get("sob_base_pct"),
    )
    return ProyeccionOut.model_validate(obj)


@router.post("/bootstrap-from-archivo", response_model=ProyeccionOut, status_code=status.HTTP_201_CREATED)
def bootstrap_from_archivo(
    granja_id: int,
    ciclo_id: int,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Factory desde un archivo importado (cuando integremos módulo de archivos).
    Por ahora: 501 Not Implemented.
    """
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)

    obj = proyeccion_service.bootstrap_from_archivo(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        archivo_id=payload.get("archivo_id"),
        version=payload.get("version"),
        descripcion=payload.get("descripcion"),
    )
    return ProyeccionOut.model_validate(obj)


# ---------------- Publicar / set current ----------------

@router.post("/{proyeccion_id}/publicar", response_model=ProyeccionOut, status_code=status.HTTP_200_OK)
def publicar_proyeccion(
    granja_id: int,
    ciclo_id: int,
    proyeccion_id: int,
    set_current: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)

    obj = proyeccion_service.publish_proyeccion(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        proyeccion_id=proyeccion_id,
        set_current=set_current,
    )
    return ProyeccionOut.model_validate(obj)


@router.post("/{proyeccion_id}/set-current", response_model=ProyeccionOut, status_code=status.HTTP_200_OK)
def set_current_proyeccion(
    granja_id: int,
    ciclo_id: int,
    proyeccion_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)

    obj = proyeccion_service.set_current(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        proyeccion_id=proyeccion_id,
    )
    return ProyeccionOut.model_validate(obj)


# ---------------- Líneas (gráficos/edición masiva) ----------------

@router.get("/{proyeccion_id}/lineas", response_model=List[ProyeccionLineaOut], status_code=status.HTTP_200_OK)
def list_lineas(
    granja_id: int,
    ciclo_id: int,
    proyeccion_id: int,
    order_by: str = Query("semana_idx", pattern="^(semana_idx|fecha_plan|pp_g)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    items = proyeccion_service.list_lineas(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        proyeccion_id=proyeccion_id,
        order_by=order_by,
        order=order,
    )
    return [ProyeccionLineaOut.model_validate(i) for i in items]


@router.put("/{proyeccion_id}/lineas:replace", response_model=ProyeccionOut, status_code=status.HTTP_200_OK)
def replace_lineas(
    granja_id: int,
    ciclo_id: int,
    proyeccion_id: int,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Reemplaza TODAS las líneas de la proyección por `items` (lista).
    Cada item debe incluir al menos: fecha_plan (YYYY-MM-DD), semana_idx, edad_dias, pp_g.
    """
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)

    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        raise ValueError("items_required")

    obj = proyeccion_service.replace_lineas(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        proyeccion_id=proyeccion_id,
        items=items,
    )
    return ProyeccionOut.model_validate(obj)


# ---------------- Borrar proyección (opcional) ----------------

@router.delete("/{proyeccion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_proyeccion(
    granja_id: int,
    ciclo_id: int,
    proyeccion_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ensure_roles(current_user, [Role.admin_global])
    ensure_visibility_granja(db, current_user, granja_id)

    proyeccion_service.delete_proyeccion(
        db=db,
        user=current_user,
        granja_id=granja_id,
        ciclo_id=ciclo_id,
        proyeccion_id=proyeccion_id,
    )
    return None
