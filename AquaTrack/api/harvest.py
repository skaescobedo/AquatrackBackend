from __future__ import annotations
from fastapi import APIRouter, Depends, Path, status, HTTPException
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import (
    ensure_user_in_farm_or_admin,
    ensure_user_has_scope,
    Scopes
)

from models.user import Usuario
from models.cycle import Ciclo
from models.harvest import CosechaOla, CosechaEstanque

from schemas.harvest import (
    HarvestWaveCreate, HarvestWaveOut, HarvestWaveWithItemsOut, HarvestEstanqueOut,
    HarvestReprogramIn, HarvestConfirmIn
)
from services.harvest_service import (
    create_wave_and_autolines, list_waves, get_wave_with_items,
    reprogram_line_date, confirm_line, cancel_wave
)
from services.reforecast_service import trigger_cosecha_reforecast
from config.settings import settings

router = APIRouter(prefix="/harvest", tags=["harvest"])


@router.post(
    "/cycles/{ciclo_id}/wave",
    response_model=HarvestWaveOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear ola de cosecha",
    description=(
            "Crea una nueva ola de cosecha y genera automáticamente líneas para todos "
            "los estanques del plan de siembra del ciclo.\n\n"
            "**Distribución automática:**\n"
            "- Las fechas se distribuyen uniformemente entre `ventana_inicio` y `ventana_fin`\n"
            "- Se crea una línea por cada estanque del plan de siembras\n\n"
            "**Tipos de ola:**\n"
            "- `'p'`: Parcial (retiro parcial de organismos)\n"
            "- `'f'`: Final (cosecha completa del estanque)\n\n"
            "**Status inicial:**\n"
            "- Ola: 'p' (planeada)\n"
            "- Líneas: 'p' (pendientes)"
    )
)
def post_harvest_wave(
        ciclo_id: int = Path(..., gt=0, description="ID del ciclo"),
        payload: HarvestWaveCreate = ...,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Crear ola de cosecha para un ciclo.

    Permisos:
    - Admin Global: Puede crear en cualquier granja
    - Admin Granja o Biólogo con gestionar_cosechas: Puede crear en su granja
    """
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    # 1. Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    # 2. Validar scope (gestionar_cosechas)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.GESTIONAR_COSECHAS,
        current_user.is_admin_global
    )

    # 3. Crear ola
    ola = create_wave_and_autolines(
        db=db,
        ciclo_id=ciclo_id,
        payload=payload,
        created_by_user_id=current_user.usuario_id
    )
    return ola


@router.get(
    "/cycles/{ciclo_id}/waves",
    response_model=list[HarvestWaveOut],
    summary="Listar olas de cosecha",
    description=(
            "Lista todas las olas de cosecha de un ciclo.\n\n"
            "Ordenadas por:\n"
            "1. Orden manual (campo `orden`)\n"
            "2. Fecha de creación"
    )
)
def get_harvest_waves(
        ciclo_id: int = Path(..., gt=0, description="ID del ciclo"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Listar olas de cosecha de un ciclo.

    Lectura implícita: Solo requiere membership en la granja.
    """
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    # Solo validar membership (lectura implícita)
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    return list_waves(db, ciclo_id)


@router.get(
    "/waves/{cosecha_ola_id}",
    response_model=HarvestWaveWithItemsOut,
    summary="Obtener ola de cosecha",
    description=(
            "Obtiene el detalle de una ola de cosecha con todas sus líneas.\n\n"
            "**Response incluye:**\n"
            "- Datos de la ola (nombre, tipo, ventanas, objetivo de retiro)\n"
            "- Lista de todas las líneas con sus estanques\n"
            "- Status de cada línea: 'p' (pendiente), 'c' (confirmada), 'x' (cancelada)"
    )
)
def get_harvest_wave(
        cosecha_ola_id: int = Path(..., gt=0, description="ID de la ola"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Obtener ola de cosecha con sus líneas.

    Lectura implícita: Solo requiere membership en la granja.
    """
    ola = get_wave_with_items(db, cosecha_ola_id)

    cycle = db.get(Ciclo, ola.ciclo_id)

    # Solo validar membership (lectura implícita)
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    return ola


@router.post(
    "/waves/{cosecha_ola_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancelar ola de cosecha",
    description=(
            "Cancela una ola completa de cosecha.\n\n"
            "**Efectos:**\n"
            "- Marca la ola con status='x' (cancelada)\n"
            "- Cancela todas las líneas pendientes (status='p' → 'x')\n"
            "- Respeta líneas ya confirmadas (status='c' no cambia)\n\n"
            "**Casos de uso típicos:**\n"
            "- Clima adverso impide cosecha planificada\n"
            "- Cambio de estrategia comercial\n"
            "- Problema sanitario en la granja"
    )
)
def post_cancel_wave(
        cosecha_ola_id: int = Path(..., gt=0, description="ID de la ola a cancelar"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Cancelar ola de cosecha completa.

    Permisos:
    - Admin Global: Puede cancelar en cualquier granja
    - Admin Granja o Biólogo con gestionar_cosechas: Puede cancelar en su granja
    """
    ola = db.get(CosechaOla, cosecha_ola_id)
    if not ola:
        raise HTTPException(status_code=404, detail="Ola no encontrada")

    cycle = db.get(Ciclo, ola.ciclo_id)

    # 1. Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    # 2. Validar scope (gestionar_cosechas)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.GESTIONAR_COSECHAS,
        current_user.is_admin_global
    )

    # 3. Cancelar ola
    return cancel_wave(db, cosecha_ola_id)


@router.post(
    "/harvests/{cosecha_estanque_id}/reprogram",
    response_model=HarvestEstanqueOut,
    summary="Reprogramar línea de cosecha",
    description=(
            "Reprograma la fecha de una línea de cosecha.\n\n"
            "**Efectos automáticos:**\n"
            "- Registra el cambio en `cosecha_fecha_log` (auditoría)\n"
            "- Si la ola estaba en status='p', la marca como 'r' (reprogramada)\n"
            "- **Trigger de reforecast**: Actualiza proyección si está habilitado\n\n"
            "**Restricciones:**\n"
            "- No permite reprogramar cosechas ya confirmadas (status='c')"
    )
)
def post_reprogram_line(
        cosecha_estanque_id: int = Path(..., gt=0, description="ID de la cosecha del estanque"),
        payload: HarvestReprogramIn = ...,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Reprogramar línea de cosecha.

    Permisos:
    - Admin Global: Puede reprogramar en cualquier granja
    - Admin Granja o Biólogo con gestionar_cosechas: Puede reprogramar en su granja
    """
    line = db.get(CosechaEstanque, cosecha_estanque_id)
    if not line:
        raise HTTPException(status_code=404, detail="Línea de cosecha no encontrada")

    ola = db.get(CosechaOla, line.cosecha_ola_id)
    cycle = db.get(Ciclo, ola.ciclo_id)

    # 1. Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    # 2. Validar scope (gestionar_cosechas)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.GESTIONAR_COSECHAS,
        current_user.is_admin_global
    )

    # 3. Reprogramar línea
    fecha_anterior = line.fecha_cosecha
    reprogrammed_line = reprogram_line_date(
        db,
        cosecha_estanque_id,
        payload,
        changed_by_user_id=current_user.usuario_id
    )

    # Trigger de reforecast si cambió la fecha
    if getattr(settings, 'REFORECAST_ENABLED', True) and fecha_anterior != payload.fecha_nueva:
        try:
            trigger_cosecha_reforecast(
                db=db,
                user=current_user,
                ciclo_id=ola.ciclo_id,
                fecha_cosecha_real=payload.fecha_nueva,
                densidad_retirada_org_m2=0.0,  # No hay retiro en reprogramación
                soft_if_other_draft=True
            )
        except Exception as e:
            print(f"⚠️ Reforecast failed: {str(e)}")

    return reprogrammed_line


@router.post(
    "/harvests/{cosecha_estanque_id}/confirm",
    response_model=HarvestEstanqueOut,
    summary="Confirmar cosecha",
    description=(
            "Confirma una línea de cosecha con datos reales.\n\n"
            "**Lógica automática:**\n"
            "1. Obtiene PP de la última biometría del estanque\n"
            "2. Si provees `biomasa_kg` → deriva `densidad_retirada_org_m2`\n"
            "3. Si provees `densidad_retirada_org_m2` → deriva `biomasa_kg`\n"
            "4. Actualiza SOB operativo del estanque\n"
            "5. Marca status='c' (confirmada)\n"
            "6. Registra timestamp de confirmación\n"
            "7. **Trigger de reforecast**: Actualiza proyección automáticamente\n\n"
            "**Fórmulas:**\n"
            "```\n"
            "densidad = (biomasa_kg × 1000) / (pp_g × area_m2)\n"
            "biomasa = (densidad × area_m2 × pp_g) / 1000\n"
            "SOB_después = SOB_antes × (1 - retiro/densidad_base)\n"
            "```\n\n"
            "**Nota:** Debes proveer SOLO UNO de: `biomasa_kg` o `densidad_retirada_org_m2`"
    )
)
def post_confirm_line(
        cosecha_estanque_id: int = Path(..., gt=0, description="ID de la cosecha del estanque"),
        payload: HarvestConfirmIn = ...,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Confirmar cosecha con datos reales (operación crítica).

    Permisos:
    - Admin Global: Puede confirmar en cualquier granja
    - Admin Granja o Biólogo con gestionar_cosechas: Puede confirmar en su granja
    """
    line = db.get(CosechaEstanque, cosecha_estanque_id)
    if not line:
        raise HTTPException(status_code=404, detail="Línea de cosecha no encontrada")

    ola = db.get(CosechaOla, line.cosecha_ola_id)
    cycle = db.get(Ciclo, ola.ciclo_id)

    # 1. Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    # 2. Validar scope (gestionar_cosechas)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.GESTIONAR_COSECHAS,
        current_user.is_admin_global
    )

    # 3. Confirmar cosecha
    confirmed_line = confirm_line(
        db,
        cosecha_estanque_id,
        payload,
        confirmed_by_user_id=current_user.usuario_id
    )

    # Trigger de reforecast
    if getattr(settings, 'REFORECAST_ENABLED', True):
        try:
            fecha_real = confirmed_line.fecha_cosecha_real or confirmed_line.fecha_cosecha
            densidad = float(confirmed_line.densidad_retirada_org_m2 or 0)

            trigger_cosecha_reforecast(
                db=db,
                user=current_user,
                ciclo_id=ola.ciclo_id,
                fecha_cosecha_real=fecha_real,
                densidad_retirada_org_m2=densidad,
                soft_if_other_draft=True
            )
        except Exception as e:
            print(f"⚠️ Reforecast failed: {str(e)}")

    return confirmed_line