from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import ensure_user_in_farm_or_admin

from models.user import Usuario
from models.cycle import Ciclo
from models.seeding import SiembraPlan, SiembraEstanque

from schemas.seeding import (
    SeedingPlanCreate, SeedingPlanOut, SeedingPlanWithItemsOut,
    SeedingCreateForPond, SeedingOut, SeedingReprogramIn, SeedingFechaLogOut
)
from services.seeding_service import (
    create_plan_and_autoseed,
    get_plan_with_items_by_cycle,
    create_manual_seeding_for_pond,
    reprogram_seeding,
    confirm_seeding,
    delete_plan_if_no_confirmed,
    get_plan_status
)
from services.reforecast_service import trigger_siembra_reforecast
from config.settings import settings

router = APIRouter(prefix="/seeding", tags=["seeding"])


@router.post(
    "/cycles/{ciclo_id}/plan",
    response_model=SeedingPlanOut,
    status_code=201,
    summary="Crear plan de siembras",
    description=(
            "Crea un plan de siembras para un ciclo y genera automáticamente las líneas de siembra "
            "para todos los estanques vigentes de la granja.\n\n"
            "**Distribución automática:**\n"
            "- Las fechas se distribuyen uniformemente entre `ventana_inicio` y `ventana_fin`\n"
            "- Solo se incluyen estanques con `is_vigente=True`\n"
            "- Se puede usar `densidad_org_m2` y `talla_inicial_g` como valores base\n\n"
            "**Restricciones:**\n"
            "- Solo puede existir un plan por ciclo\n"
            "- El plan se crea con status='p' (planeado)"
    )
)
def post_seeding_plan(
        ciclo_id: int = Path(..., gt=0, description="ID del ciclo"),
        payload: SeedingPlanCreate = ...,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    plan = create_plan_and_autoseed(db, ciclo_id, payload, user.usuario_id)
    return plan


@router.get(
    "/cycles/{ciclo_id}/plan",
    response_model=SeedingPlanWithItemsOut,
    summary="Obtener plan de siembras",
    description=(
            "Obtiene el plan de siembras de un ciclo con todas sus líneas de siembra.\n\n"
            "**Response incluye:**\n"
            "- Datos del plan (ventanas, densidad base, talla base)\n"
            "- Lista de todas las líneas de siembra con sus estanques\n"
            "- Status de cada línea: 'p' (pendiente), 'e' (en ejecución), 'f' (finalizada)"
    )
)
def get_seeding_plan(
        ciclo_id: int = Path(..., gt=0, description="ID del ciclo"),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    return get_plan_with_items_by_cycle(db, ciclo_id)


@router.post(
    "/ponds/{estanque_id}",
    response_model=SeedingOut,
    status_code=201,
    summary="Crear siembra manual para estanque",
    description=(
            "Crea una línea de siembra manual para un estanque específico.\n\n"
            "**Uso típico:**\n"
            "- Agregar estanque que no estaba en el plan original\n"
            "- Crear siembra con parámetros específicos diferentes al plan base\n\n"
            "**Parámetros opcionales:**\n"
            "- `densidad_override_org_m2`: Sobrescribe densidad del plan\n"
            "- `talla_inicial_override_g`: Sobrescribe talla del plan\n"
            "- Si no se proveen, usa los valores del plan base"
    )
)
def post_manual_seeding(
        estanque_id: int = Path(..., gt=0, description="ID del estanque"),
        payload: SeedingCreateForPond = ...,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    seed = create_manual_seeding_for_pond(db, estanque_id, payload, user.usuario_id)

    cycle = db.get(Ciclo, seed.ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    return seed


@router.post(
    "/seedings/{siembra_estanque_id}/confirm",
    response_model=SeedingOut,
    summary="Confirmar siembra",
    description=(
            "Confirma la ejecución de una siembra.\n\n"
            "**Efectos automáticos:**\n"
            "1. Marca la línea como 'f' (finalizada)\n"
            "2. Asigna `fecha_siembra` = fecha actual\n"
            "3. Activa el estanque (status='a')\n"
            "4. Si es la primera siembra: plan pasa de 'p' a 'e'\n"
            "5. **Si es la última siembra:** plan pasa a 'f' y **dispara trigger de reforecast**\n\n"
            "**Trigger de Reforecast:**\n"
            "- Se ejecuta SOLO cuando se confirma la última siembra del plan\n"
            "- Usa la fecha de la última siembra confirmada como `siembra_ventana_fin`\n"
            "- Actualiza la primera línea de proyección con esta fecha\n"
            "- Si hay borrador manual, NO lo sobrescribe (modo soft)"
    )
)
def post_confirm_seeding(
        siembra_estanque_id: int = Path(..., gt=0, description="ID de la siembra del estanque"),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    line = db.get(SiembraEstanque, siembra_estanque_id)
    if not line:
        raise HTTPException(status_code=404, detail="Línea de siembra no encontrada")

    plan = db.get(SiembraPlan, line.siembra_plan_id)
    cycle = db.get(Ciclo, plan.ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    # Guardar ventana_fin original (tentativa) antes de actualizar
    ventana_fin_original = plan.ventana_fin

    # Confirmar la siembra
    confirmed_line = confirm_seeding(db, siembra_estanque_id, user.usuario_id)

    # Verificar si el plan pasó a 'f' (finalizado)
    # Refresh del plan para obtener el status y ventanas actualizadas
    db.refresh(plan)

    # Trigger de reforecast SOLO si el plan pasó a 'f'
    if plan.status == "f" and getattr(settings, 'REFORECAST_ENABLED', True):
        try:
            # Usar la ventana_fin actualizada del plan (última siembra confirmada)
            reforecast_result = trigger_siembra_reforecast(
                db=db,
                user=user,
                ciclo_id=plan.ciclo_id,
                fecha_siembra_real=plan.ventana_fin,  # Fecha real de última siembra
                fecha_siembra_tentativa=ventana_fin_original,  # Fecha tentativa original
                soft_if_other_draft=True
            )

            if reforecast_result and not reforecast_result.get("skipped"):
                print(f"✅ Reforecast triggered: All seedings confirmed for cycle {plan.ciclo_id}")

        except Exception as e:
            print(f"⚠️ Reforecast failed after seeding plan finalized: {str(e)}")

    return confirmed_line


@router.post(
    "/seedings/{siembra_estanque_id}/reprogram",
    response_model=SeedingOut,
    summary="Reprogramar siembra",
    description=(
            "Reprograma la fecha u otros parámetros de una siembra pendiente.\n\n"
            "**Semántica del payload:**\n"
            "- `null` en cualquier campo → NO cambia ese valor\n"
            "- `0` en densidad/talla → NO cambia (ignorado)\n"
            "- Valor válido distinto de 0 → ACTUALIZA\n"
            "- Para `lote`: null → no cambia; string (incluida `\"\"`) → se asigna/limpia\n\n"
            "**Registro de cambios:**\n"
            "- Si la fecha cambia, se registra en `siembra_fecha_log`\n"
            "- Se guarda el motivo del cambio para auditoría\n\n"
            "**Restricciones:**\n"
            "- No se puede reprogramar una siembra ya confirmada (status='f')"
    ),
    openapi_extra={
        "examples": {
            "solo_fecha": {
                "summary": "Solo cambiar fecha",
                "value": {
                    "fecha_nueva": "2025-11-28",
                    "lote": None,
                    "densidad_override_org_m2": None,
                    "talla_inicial_override_g": None,
                    "motivo": "ajuste de agenda"
                }
            },
            "actualizar_todo": {
                "summary": "Actualizar todos los campos",
                "value": {
                    "fecha_nueva": "2025-11-02",
                    "lote": "L-2025A",
                    "densidad_override_org_m2": 10.25,
                    "talla_inicial_override_g": 1.8,
                    "motivo": "replanificación completa"
                }
            }
        }
    }
)
def post_reprogram_seeding(
        siembra_estanque_id: int = Path(..., gt=0, description="ID de la siembra del estanque"),
        payload: SeedingReprogramIn = ...,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    line = db.get(SiembraEstanque, siembra_estanque_id)
    if not line:
        raise HTTPException(status_code=404, detail="Línea de siembra no encontrada")

    plan = db.get(SiembraPlan, line.siembra_plan_id)
    cycle = db.get(Ciclo, plan.ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    reprogrammed_line = reprogram_seeding(db, siembra_estanque_id, payload, user.usuario_id)
    return reprogrammed_line


@router.get(
    "/seedings/{siembra_estanque_id}/logs",
    response_model=list[SeedingFechaLogOut],
    summary="Obtener logs de cambios de fecha",
    description=(
            "Obtiene el historial de cambios de fecha de una línea de siembra.\n\n"
            "**Información incluida:**\n"
            "- Fecha anterior y nueva\n"
            "- Motivo del cambio\n"
            "- Usuario que realizó el cambio\n"
            "- Timestamp del cambio\n\n"
            "Ordenado por fecha de cambio (más reciente primero)."
    )
)
def get_seeding_logs(
        siembra_estanque_id: int = Path(..., gt=0, description="ID de la siembra del estanque"),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    line = db.get(SiembraEstanque, siembra_estanque_id)
    if not line:
        raise HTTPException(status_code=404, detail="Línea de siembra no encontrada")

    plan = db.get(SiembraPlan, line.siembra_plan_id)
    cycle = db.get(Ciclo, plan.ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    from sqlalchemy import desc
    from models.seeding import SiembraFechaLog

    logs = (
        db.query(SiembraFechaLog)
        .filter(SiembraFechaLog.siembra_estanque_id == siembra_estanque_id)
        .order_by(desc(SiembraFechaLog.created_at))
        .all()
    )
    return logs


@router.delete(
    "/plans/{plan_id}",
    status_code=204,
    summary="Eliminar plan de siembras",
    description=(
            "Elimina un plan de siembras y todas sus líneas.\n\n"
            "**Restricción:**\n"
            "- Solo se puede eliminar si NO hay siembras confirmadas\n"
            "- Si alguna siembra tiene status='f', retorna error 409"
    )
)
def delete_seeding_plan(
        plan_id: int = Path(..., gt=0, description="ID del plan"),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    plan = db.get(SiembraPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    cycle = db.get(Ciclo, plan.ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    delete_plan_if_no_confirmed(db, plan_id)
    return None


@router.get(
    "/plans/{plan_id}/status",
    summary="Obtener status del plan",
    description=(
            "Obtiene el status del plan y estadísticas de progreso.\n\n"
            "**Response:**\n"
            "```json\n"
            "{\n"
            '  "plan_status": "e",  // p=planeado, e=en ejecución, f=finalizado\n'
            '  "total_siembras": 5,\n'
            '  "confirmadas": 3,\n'
            '  "pendientes": 2,\n'
            '  "all_confirmed": false\n'
            "}\n"
            "```\n\n"
            "**Útil para:**\n"
            "- Monitorear progreso de siembras\n"
            "- Saber cuándo se disparará el trigger de reforecast\n"
            "- Dashboard de operaciones"
    )
)
def get_plan_status_endpoint(
        plan_id: int = Path(..., gt=0, description="ID del plan"),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """Obtiene el status del plan y estadísticas de siembras"""
    plan = db.get(SiembraPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    cycle = db.get(Ciclo, plan.ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db, user.usuario_id, cycle.granja_id, user.is_admin_global
    )

    return get_plan_status(db, plan_id)