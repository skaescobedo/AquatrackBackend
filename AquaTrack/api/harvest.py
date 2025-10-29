from __future__ import annotations
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import ensure_user_in_farm_or_admin

from models.user import Usuario
from models.cycle import Ciclo

from schemas.harvest import (
    HarvestWaveCreate, HarvestWaveOut, HarvestWaveWithItemsOut, HarvestEstanqueOut,
    HarvestReprogramIn, HarvestConfirmIn
)
from services.harvest_service import (
    create_wave_and_autolines, list_waves, get_wave_with_items,
    reprogram_line_date, confirm_line, cancel_wave
)

router = APIRouter(prefix="/harvest", tags=["harvest"])


# ==========================================
# OLAS (Waves)
# ==========================================

@router.post("/cycles/{ciclo_id}/wave", response_model=HarvestWaveOut, status_code=status.HTTP_201_CREATED)
def post_harvest_wave(
        ciclo_id: int = Path(..., gt=0, description="ID del ciclo"),
        payload: HarvestWaveCreate = ...,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """
    Crea una nueva ola de cosecha y genera automáticamente líneas para todos
    los estanques del plan de siembra del ciclo.
    """
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)
    return create_wave_and_autolines(db, ciclo_id, payload, created_by_user_id=user.usuario_id)


@router.get("/cycles/{ciclo_id}/waves", response_model=list[HarvestWaveOut])
def get_harvest_waves(
        ciclo_id: int = Path(..., gt=0, description="ID del ciclo"),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """
    Lista todas las olas de cosecha de un ciclo.
    """
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)
    return list_waves(db, ciclo_id)


@router.get("/waves/{cosecha_ola_id}", response_model=HarvestWaveWithItemsOut)
def get_harvest_wave(
        cosecha_ola_id: int = Path(..., gt=0, description="ID de la ola"),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """
    Obtiene el detalle de una ola con todas sus líneas de cosecha.
    """
    ola = get_wave_with_items(db, cosecha_ola_id)

    # Permisos por granja del ciclo
    cycle = db.get(Ciclo, ola.ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)
    return ola


@router.post("/waves/{cosecha_ola_id}/cancel", status_code=status.HTTP_200_OK)
def post_cancel_wave(
        cosecha_ola_id: int = Path(..., gt=0, description="ID de la ola a cancelar"),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """
    Cancela una ola completa:
    - Marca la ola con status='x'
    - Cancela todas las líneas pendientes (status='p')
    - Respeta líneas ya confirmadas (status='c')

    Casos de uso:
    - Clima adverso impide cosecha planificada
    - Cambio de estrategia comercial
    - Problema sanitario en la granja
    """
    # Cargar ola para validar permisos
    from models.harvest import CosechaOla
    ola = db.get(CosechaOla, cosecha_ola_id)
    if not ola:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ola no encontrada")

    cycle = db.get(Ciclo, ola.ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    return cancel_wave(db, cosecha_ola_id)


# ==========================================
# LÍNEAS DE COSECHA (Harvest Lines)
# ==========================================

@router.post("/lines/{cosecha_estanque_id}/reprogram", response_model=HarvestEstanqueOut)
def post_reprogram_line(
        cosecha_estanque_id: int = Path(..., gt=0, description="ID de la línea de cosecha"),
        payload: HarvestReprogramIn = ...,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """
    Reprograma la fecha de una línea de cosecha.

    - Registra el cambio en cosecha_fecha_log (auditoría)
    - Si la ola estaba en status='p', la marca como 'r' (reprogramada)
    - No permite reprogramar cosechas ya confirmadas
    """
    # Validar permisos antes de reprogramar
    from models.harvest import CosechaOla, CosechaEstanque
    line = db.get(CosechaEstanque, cosecha_estanque_id)
    if not line:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Línea de cosecha no encontrada")

    ola = db.get(CosechaOla, line.cosecha_ola_id)
    cycle = db.get(Ciclo, ola.ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    return reprogram_line_date(db, cosecha_estanque_id, payload, changed_by_user_id=user.usuario_id)


@router.post("/lines/{cosecha_estanque_id}/confirm", response_model=HarvestEstanqueOut)
def post_confirm_line(
        cosecha_estanque_id: int = Path(..., gt=0, description="ID de la línea de cosecha"),
        payload: HarvestConfirmIn = ...,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """
    Confirma una línea de cosecha con datos reales.

    Lógica automática:
    - Obtiene PP de la última biometría del estanque
    - Si provees biomasa_kg → deriva densidad_retirada_org_m2
    - Si provees densidad_retirada_org_m2 → deriva biomasa_kg
    - Marca status='c' (confirmada)
    - Registra timestamp de confirmación

    Fórmulas:
    - densidad = (biomasa_kg * 1000) / (pp_g * area_m2)
    - biomasa = (densidad * area_m2 * pp_g) / 1000
    """
    # Validar permisos
    from models.harvest import CosechaOla, CosechaEstanque
    line = db.get(CosechaEstanque, cosecha_estanque_id)
    if not line:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Línea de cosecha no encontrada")

    ola = db.get(CosechaOla, line.cosecha_ola_id)
    cycle = db.get(Ciclo, ola.ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    return confirm_line(db, cosecha_estanque_id, payload, confirmed_by_user_id=user.usuario_id)