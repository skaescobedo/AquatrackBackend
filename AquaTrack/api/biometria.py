from __future__ import annotations

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query, status, HTTPException
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import ensure_user_in_farm_or_admin

from models.user import Usuario
from models.cycle import Ciclo

from schemas.biometria import (
    BiometriaCreate,
    BiometriaUpdate,
    BiometriaOut,
    BiometriaListOut
)
from services.biometria_service import BiometriaService

router = APIRouter(prefix="/biometria", tags=["biometria"])

# ==========================================
# POST - Registrar muestra (fecha la fija el servidor)
# ==========================================

@router.post(
    "/cycles/{ciclo_id}/ponds/{estanque_id}",
    response_model=BiometriaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar biometría",
    description=(
        "Registra una nueva biometría para un estanque dentro de un ciclo.\n\n"
        "- La **fecha** se fija en el servidor en **America/Mazatlan**.\n"
        "- Calcula PP, incremento semanal y gestiona SOB operativo.\n"
        "- Si `actualiza_sob_operativa=True`, registra log del cambio de SOB."
    )
)
def create_biometria(
    ciclo_id: int = Path(..., gt=0, description="ID del ciclo"),
    estanque_id: int = Path(..., gt=0, description="ID del estanque"),
    payload: BiometriaCreate = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    bio = BiometriaService.create(
        db=db,
        ciclo_id=ciclo_id,
        estanque_id=estanque_id,
        payload=payload,
        user_id=user.usuario_id
    )
    return bio

# ==========================================
# GET - Historial del estanque
# ==========================================

@router.get(
    "/cycles/{ciclo_id}/ponds/{estanque_id}",
    response_model=List[BiometriaListOut],
    summary="Historial de biometrías de un estanque",
    description="Lista las biometrías de un estanque dentro de un ciclo, con filtros opcionales."
)
def list_biometrias_pond(
    ciclo_id: int = Path(..., gt=0),
    estanque_id: int = Path(..., gt=0),
    fecha_desde: Optional[datetime] = Query(None, description="Fecha mínima (ISO 8601). Se asume Mazatlán si es naive."),
    fecha_hasta: Optional[datetime] = Query(None, description="Fecha máxima (ISO 8601). Se asume Mazatlán si es naive."),
    limit: int = Query(100, ge=1, le=500, description="Máximo de registros"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    return BiometriaService.list_history_by_pond(
        db=db,
        ciclo_id=ciclo_id,
        estanque_id=estanque_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limit=limit,
        offset=offset
    )

# ==========================================
# GET - Detalle por ID
# ==========================================

@router.get(
    "/{biometria_id}",
    response_model=BiometriaOut,
    summary="Obtener biometría",
    description="Obtiene el detalle completo de una biometría por su ID."
)
def get_biometria(
    biometria_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    bio = BiometriaService.get_by_id(db, biometria_id)

    cycle = db.get(Ciclo, bio.ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )
    return bio

# ==========================================
# PATCH - Editar (solo notas si no actualiza SOB)
# ==========================================

@router.patch(
    "/{biometria_id}",
    response_model=BiometriaOut,
    summary="Actualizar biometría",
    description=(
        "Actualiza una biometría **solo** si NO actualizó el SOB operativo. "
        "En la práctica, permite modificar únicamente el campo `notas`."
    )
)
def update_biometria(
    biometria_id: int = Path(..., gt=0),
    payload: BiometriaUpdate = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    bio = BiometriaService.get_by_id(db, biometria_id)

    cycle = db.get(Ciclo, bio.ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    return BiometriaService.update(db, biometria_id, payload)
