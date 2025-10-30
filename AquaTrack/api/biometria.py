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
    BiometriaListOut,
    BiometriaCreateResponse,
    BiometriaContextOut
)
from services.biometria_service import BiometriaService
from services.reforecast_service import trigger_biometria_reforecast
from config.settings import settings

router = APIRouter(prefix="/biometria", tags=["biometria"])


@router.get(
    "/cycles/{ciclo_id}/ponds/{estanque_id}/context",
    response_model=BiometriaContextOut,
    summary="Obtener contexto para registrar biometría",
    description=(
        "Retorna el contexto completo necesario para el formulario de registro de biometría:\n\n"
        "- **SOB operativo actual**: Para pre-cargar el campo en el formulario\n"
        "- **Datos de siembra**: Densidad base, fecha, días de ciclo\n"
        "- **Retiros acumulados**: Cosechas confirmadas\n"
        "- **Población estimada**: Densidad efectiva y organismos totales\n"
        "- **Última biometría**: PP, SOB, días transcurridos (opcional)\n"
        "- **Proyección vigente**: Valores esperados de PP y SOB (opcional)\n\n"
        "Este endpoint debe llamarse ANTES de mostrar el formulario de registro."
    )
)
def get_biometria_context(
    ciclo_id: int = Path(..., gt=0, description="ID del ciclo"),
    estanque_id: int = Path(..., gt=0, description="ID del estanque"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    return BiometriaService.get_context_for_registration(
        db=db,
        ciclo_id=ciclo_id,
        estanque_id=estanque_id
    )


@router.post(
    "/cycles/{ciclo_id}/ponds/{estanque_id}",
    response_model=BiometriaCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar biometría",
    description=(
            "Registra una nueva biometría para un estanque dentro de un ciclo.\n\n"
            "- La **fecha** se fija en el servidor en **America/Mazatlan**.\n"
            "- Calcula PP, incremento semanal y gestiona SOB operativo.\n"
            "- Si `actualiza_sob_operativa=True`, registra log del cambio de SOB.\n"
            "- **sob_usada_pct es opcional**: Si no se provee y actualiza_sob_operativa=False, usa el SOB operativo actual.\n"
            "- **Trigger automático**: Si el reforecast está habilitado, actualiza el borrador de proyección.\n\n"
            "**Respuesta incluye**:\n"
            "- `biometria`: Datos de la biometría creada\n"
            "- `reforecast_result`: Resultado del trigger (si se ejecutó)"
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

    # Crear biometría
    bio = BiometriaService.create(
        db=db,
        ciclo_id=ciclo_id,
        estanque_id=estanque_id,
        payload=payload,
        user_id=user.usuario_id
    )

    # Trigger de reforecast con captura de resultado
    reforecast_result = None
    if settings.REFORECAST_ENABLED:
        try:
            reforecast_result = trigger_biometria_reforecast(
                db=db,
                user=user,
                ciclo_id=ciclo_id,
                fecha_bio=bio.fecha.date(),
                soft_if_other_draft=True
            )

            # Log para debugging
            if reforecast_result.get("skipped"):
                print(f"⚠️ Reforecast skipped: {reforecast_result.get('reason')}")
                print(f"   Details: {reforecast_result}")
            else:
                print(f"✅ Reforecast executed successfully")
                print(f"   Proyección ID: {reforecast_result.get('proyeccion_id')}")
                print(f"   Week anchored: {reforecast_result.get('week_idx')}")

        except Exception as e:
            print(f"❌ Reforecast failed with exception: {str(e)}")
            import traceback
            traceback.print_exc()
            # No fallar el endpoint, solo registrar el error
            reforecast_result = {
                "skipped": True,
                "reason": "exception",
                "error": str(e)
            }

    return BiometriaCreateResponse(
        biometria=bio,
        reforecast_result=reforecast_result
    )


@router.get(
    "/cycles/{ciclo_id}/ponds/{estanque_id}",
    response_model=List[BiometriaListOut],
    summary="Historial de biometrías de un estanque",
    description="Lista las biometrías de un estanque dentro de un ciclo, con filtros opcionales."
)
def list_biometrias_pond(
        ciclo_id: int = Path(..., gt=0),
        estanque_id: int = Path(..., gt=0),
        fecha_desde: Optional[datetime] = Query(None,
                                                description="Fecha mínima (ISO 8601). Se asume Mazatlán si es naive."),
        fecha_hasta: Optional[datetime] = Query(None,
                                                description="Fecha máxima (ISO 8601). Se asume Mazatlán si es naive."),
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


@router.get(
    "/cycles/{ciclo_id}",
    response_model=List[BiometriaListOut],
    summary="Historial de biometrías de todo el ciclo",
    description="Lista todas las biometrías del ciclo (todos los estanques), con filtros opcionales."
)
def list_biometrias_cycle(
        ciclo_id: int = Path(..., gt=0),
        fecha_desde: Optional[datetime] = Query(None),
        fecha_hasta: Optional[datetime] = Query(None),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
):
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    return BiometriaService.list_history_by_cycle(
        db=db,
        ciclo_id=ciclo_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limit=limit,
        offset=offset
    )


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


@router.delete(
    "/{biometria_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar biometría",
    description=(
            "Elimina una biometría si:\n"
            "- NO actualizó el SOB operativo, o\n"
            "- Existen biometrías posteriores que restablecieron el SOB."
    )
)
def delete_biometria(
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

    BiometriaService.delete(db, biometria_id)
    return None