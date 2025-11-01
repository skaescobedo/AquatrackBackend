# api/tasks.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status, HTTPException
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import ensure_user_in_farm_or_admin

from models.user import Usuario
from models.farm import Granja
from models.task import Tarea

from schemas.task import (
    TareaCreate, TareaUpdate, TareaUpdateStatus,
    TareaOut, TareaListOut
)
from services.task_service import (
    create_task, get_task, update_task, update_task_status, delete_task,
    duplicate_task, get_tasks_by_farm, get_user_tasks, get_overdue_tasks,
    _can_user_complete_task
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ============================================================================
# CRUD Básico
# ============================================================================

@router.post(
    "/farms/{granja_id}",
    response_model=TareaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva tarea",
    description=(
            "Crea una nueva tarea en una granja.\n\n"
            "**Características:**\n"
            "- Vinculación opcional con ciclo/estanque\n"
            "- Asignación múltiple de usuarios (campo `asignados_ids`)\n"
            "- Si no se asignan usuarios, el creador es responsable por defecto\n"
            "- Status inicial: 'p' (pendiente), progreso: 0%\n\n"
            "**Prioridades:**\n"
            "- `'b'`: Baja\n"
            "- `'m'`: Media (default)\n"
            "- `'a'`: Alta\n\n"
            "**Flag recurrente:**\n"
            "- `es_recurrente=true`: Permite duplicar la tarea fácilmente"
    )
)
def create_task_endpoint(
        granja_id: int = Path(..., gt=0, description="ID de la granja"),
        task_data: TareaCreate = ...,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """Crear nueva tarea en una granja"""
    # Validar que la granja existe
    granja = db.get(Granja, granja_id)
    if not granja:
        raise HTTPException(status_code=404, detail="Granja no encontrada")

    # Validar que el usuario tiene acceso a la granja
    ensure_user_in_farm_or_admin(
        db, current_user.usuario_id, granja_id, current_user.is_admin_global
    )

    # Forzar granja_id del path en el payload
    task_data.granja_id = granja_id

    return create_task(db, task_data, current_user.usuario_id)


@router.get(
    "/{tarea_id}",
    response_model=TareaOut,
    summary="Obtener detalle de tarea",
    description=(
            "Obtiene el detalle completo de una tarea.\n\n"
            "**Response incluye:**\n"
            "- Datos básicos de la tarea\n"
            "- Información del creador\n"
            "- Lista de usuarios asignados\n"
            "- Campos computados: responsables_nombres, dias_restantes, is_vencida\n\n"
            "**Permisos:**\n"
            "- Usuario debe tener acceso a la granja de la tarea"
    )
)
def get_task_endpoint(
        tarea_id: int = Path(..., gt=0, description="ID de la tarea"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """Obtener detalle de tarea"""
    tarea = get_task(db, tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Validar acceso a la granja (si tiene granja)
    if tarea.granja_id:
        ensure_user_in_farm_or_admin(
            db, current_user.usuario_id, tarea.granja_id, current_user.is_admin_global
        )

    return tarea


@router.patch(
    "/{tarea_id}",
    response_model=TareaOut,
    summary="Actualizar tarea",
    description=(
            "Actualiza una tarea existente.\n\n"
            "**Campos actualizables:**\n"
            "- Datos básicos: titulo, descripcion, tipo\n"
            "- Clasificación: prioridad, status\n"
            "- Temporalidad: fecha_limite, tiempo_estimado_horas\n"
            "- Progreso: progreso_pct (0-100)\n"
            "- Asignaciones: asignados_ids (reemplaza todas las asignaciones)\n\n"
            "**Lógica automática:**\n"
            "- Si `status='c'` (completada) → `progreso_pct=100` automáticamente\n"
            "- Si se provee `asignados_ids`, se eliminan asignaciones previas\n\n"
            "**Permisos:**\n"
            "- Usuario debe tener acceso a la granja de la tarea"
    )
)
def update_task_endpoint(
        tarea_id: int = Path(..., gt=0, description="ID de la tarea"),
        task_data: TareaUpdate = ...,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """Actualizar tarea"""
    # Validar que la tarea existe
    tarea = get_task(db, tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Validar acceso a la granja
    if tarea.granja_id:
        ensure_user_in_farm_or_admin(
            db, current_user.usuario_id, tarea.granja_id, current_user.is_admin_global
        )

    return update_task(db, tarea_id, task_data)


@router.patch(
    "/{tarea_id}/status",
    response_model=TareaOut,
    summary="Actualizar status de tarea (rápido)",
    description=(
            "Actualiza solo el status y progreso de una tarea.\n\n"
            "**Operación optimizada** para cambios rápidos de estado:\n"
            "- Marcar tarea como 'e' (en progreso)\n"
            "- Completar tarea: 'c' (completada)\n"
            "- Cancelar tarea: 'x' (cancelada)\n\n"
            "**Lógica automática:**\n"
            "- Si `status='c'` → `progreso_pct=100` automáticamente\n\n"
            "**Estados válidos:**\n"
            "- `'p'`: Pendiente\n"
            "- `'e'`: En progreso\n"
            "- `'c'`: Completada\n"
            "- `'x'`: Cancelada\n\n"
            "**Permisos especiales:**\n"
            "- Usuario debe ser responsable de la tarea:\n"
            "  - Estar en asignaciones, O\n"
            "  - Ser creador (si no hay asignaciones)"
    )
)
def update_task_status_endpoint(
        tarea_id: int = Path(..., gt=0, description="ID de la tarea"),
        status_data: TareaUpdateStatus = ...,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """Actualizar solo status y progreso (operación rápida)"""
    # Validar que la tarea existe
    tarea = get_task(db, tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Validar acceso a la granja
    if tarea.granja_id:
        ensure_user_in_farm_or_admin(
            db, current_user.usuario_id, tarea.granja_id, current_user.is_admin_global
        )

    # Validar que el usuario puede completar la tarea
    if not _can_user_complete_task(tarea, current_user.usuario_id):
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para actualizar el status de esta tarea. Debes ser responsable (asignado o creador)."
        )

    return update_task_status(db, tarea_id, status_data)


@router.delete(
    "/{tarea_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar tarea",
    description=(
            "Elimina una tarea de forma permanente.\n\n"
            "**Efectos en cascada:**\n"
            "- Se eliminan automáticamente todas las asignaciones\n"
            "- No se pueden eliminar tareas ya completadas (validación futura)\n\n"
            "**Permisos:**\n"
            "- Solo el creador de la tarea puede eliminarla\n"
            "- O usuarios admin globales"
    )
)
def delete_task_endpoint(
        tarea_id: int = Path(..., gt=0, description="ID de la tarea"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """Eliminar tarea"""
    # Validar que la tarea existe
    tarea = get_task(db, tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Validar acceso a la granja
    if tarea.granja_id:
        ensure_user_in_farm_or_admin(
            db, current_user.usuario_id, tarea.granja_id, current_user.is_admin_global
        )

    # Validar que solo el creador o admin puede eliminar
    if tarea.created_by != current_user.usuario_id and not current_user.is_admin_global:
        raise HTTPException(
            status_code=403,
            detail="Solo el creador de la tarea puede eliminarla"
        )

    delete_task(db, tarea_id)
    return None


@router.post(
    "/{tarea_id}/duplicate",
    response_model=TareaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicar tarea",
    description=(
            "Duplica una tarea existente (útil para tareas recurrentes).\n\n"
            "**Campos copiados:**\n"
            "- titulo, descripcion, tipo\n"
            "- prioridad, tiempo_estimado_horas\n"
            "- es_recurrente\n"
            "- granja_id, ciclo_id, estanque_id\n"
            "- asignaciones (mismos usuarios)\n\n"
            "**Campos NO copiados (valores por defecto):**\n"
            "- fecha_limite: `null`\n"
            "- progreso_pct: `0`\n"
            "- status: `'p'` (pendiente)\n"
            "- created_at: fecha actual\n"
            "- created_by: usuario que duplica\n\n"
            "**Caso de uso típico:**\n"
            "- Tareas semanales/mensuales (biometrías, mantenimiento)\n"
            "- Marcar tarea original con `es_recurrente=true`"
    )
)
def duplicate_task_endpoint(
        tarea_id: int = Path(..., gt=0, description="ID de la tarea a duplicar"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """Duplicar tarea (útil para recurrentes)"""
    # Validar que la tarea existe
    tarea = get_task(db, tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Validar acceso a la granja
    if tarea.granja_id:
        ensure_user_in_farm_or_admin(
            db, current_user.usuario_id, tarea.granja_id, current_user.is_admin_global
        )

    return duplicate_task(db, tarea_id, current_user.usuario_id)


# ============================================================================
# Queries y Filtros
# ============================================================================

@router.get(
    "/farms/{granja_id}",
    response_model=list[TareaListOut],
    summary="Listar tareas de una granja",
    description=(
            "Lista tareas de una granja con filtros opcionales.\n\n"
            "**Filtros disponibles:**\n"
            "- `status`: Filtrar por estado (p/e/c/x)\n"
            "- `asignado_a`: Tareas donde el usuario está asignado O es creador\n"
            "- `ciclo_id`: Tareas de un ciclo específico\n\n"
            "**Paginación:**\n"
            "- `skip`: Número de registros a saltar (default: 0)\n"
            "- `limit`: Máximo de registros a retornar (default: 100, max: 500)\n\n"
            "**Orden:**\n"
            "- Ordenado por fecha de creación descendente (más recientes primero)\n\n"
            "**Response simplificado:**\n"
            "- Solo campos esenciales para listas\n"
            "- Incluye conteo de asignados y nombres de responsables"
    )
)
def list_farm_tasks_endpoint(
        granja_id: int = Path(..., gt=0, description="ID de la granja"),
        status: str | None = Query(None, regex="^[pecx]$", description="Filtrar por status (p/e/c/x)"),
        asignado_a: int | None = Query(None, gt=0, description="Filtrar por usuario asignado o creador"),
        ciclo_id: int | None = Query(None, gt=0, description="Filtrar por ciclo"),
        skip: int = Query(0, ge=0, description="Registros a saltar (paginación)"),
        limit: int = Query(100, ge=1, le=500, description="Máximo de registros (max: 500)"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """Listar tareas de una granja con filtros opcionales"""
    # Validar que la granja existe
    granja = db.get(Granja, granja_id)
    if not granja:
        raise HTTPException(status_code=404, detail="Granja no encontrada")

    # Validar acceso a la granja
    ensure_user_in_farm_or_admin(
        db, current_user.usuario_id, granja_id, current_user.is_admin_global
    )

    tareas = get_tasks_by_farm(
        db=db,
        granja_id=granja_id,
        status=status,
        asignado_a=asignado_a,
        ciclo_id=ciclo_id,
        skip=skip,
        limit=limit
    )

    # Convertir a TareaListOut usando el método personalizado
    return [TareaListOut.from_tarea(tarea) for tarea in tareas]


@router.get(
    "/users/{usuario_id}/tasks",
    response_model=list[TareaListOut],
    summary="Listar tareas de un usuario",
    description=(
            "Lista todas las tareas de un usuario (asignadas o creadas).\n\n"
            "**Lógica de inclusión:**\n"
            "- Tareas donde está asignado (en `tarea_asignacion`)\n"
            "- Tareas que creó sin asignaciones (si `include_created=true`)\n\n"
            "**Filtros disponibles:**\n"
            "- `granja_id`: Limitar a tareas de una granja específica\n"
            "- `status`: Filtrar por estado (p/e/c/x)\n"
            "- `include_created`: Incluir tareas creadas sin asignaciones (default: true)\n\n"
            "**Paginación:**\n"
            "- `skip`: Número de registros a saltar (default: 0)\n"
            "- `limit`: Máximo de registros a retornar (default: 100, max: 500)\n\n"
            "**Permisos:**\n"
            "- Usuarios normales solo pueden ver sus propias tareas\n"
            "- Admins globales pueden ver tareas de cualquier usuario"
    )
)
def list_user_tasks_endpoint(
        usuario_id: int = Path(..., gt=0, description="ID del usuario"),
        granja_id: int | None = Query(None, gt=0, description="Filtrar por granja"),
        status: str | None = Query(None, regex="^[pecx]$", description="Filtrar por status (p/e/c/x)"),
        include_created: bool = Query(True, description="Incluir tareas creadas sin asignaciones"),
        skip: int = Query(0, ge=0, description="Registros a saltar (paginación)"),
        limit: int = Query(100, ge=1, le=500, description="Máximo de registros (max: 500)"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """Listar tareas de un usuario"""
    # Validar que el usuario existe
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Validar permisos: solo puede ver sus propias tareas (excepto admins)
    if usuario_id != current_user.usuario_id and not current_user.is_admin_global:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para ver las tareas de otro usuario"
        )

    tareas = get_user_tasks(
        db=db,
        usuario_id=usuario_id,
        granja_id=granja_id,
        status=status,
        include_created=include_created,
        skip=skip,
        limit=limit
    )

    # Convertir a TareaListOut usando el método personalizado
    return [TareaListOut.from_tarea(tarea) for tarea in tareas]


@router.get(
    "/farms/{granja_id}/overdue",
    response_model=list[TareaListOut],
    summary="Listar tareas vencidas",
    description=(
            "Lista todas las tareas vencidas de una granja.\n\n"
            "**Criterios de vencimiento:**\n"
            "- `fecha_limite < HOY`\n"
            "- `status != 'c'` (no completadas)\n"
            "- `status != 'x'` (no canceladas)\n\n"
            "**Orden:**\n"
            "- Ordenado por fecha límite ascendente (más urgentes primero)\n\n"
            "**Caso de uso típico:**\n"
            "- Dashboard de tareas atrasadas\n"
            "- Alertas y notificaciones\n"
            "- Reportes de cumplimiento"
    )
)
def list_overdue_tasks_endpoint(
        granja_id: int = Path(..., gt=0, description="ID de la granja"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """Listar tareas vencidas de la granja"""
    # Validar que la granja existe
    granja = db.get(Granja, granja_id)
    if not granja:
        raise HTTPException(status_code=404, detail="Granja no encontrada")

    # Validar acceso a la granja
    ensure_user_in_farm_or_admin(
        db, current_user.usuario_id, granja_id, current_user.is_admin_global
    )

    tareas = get_overdue_tasks(db, granja_id)

    # Convertir a TareaListOut usando el método personalizado
    return [TareaListOut.from_tarea(tarea) for tarea in tareas]


# ============================================================================
# Dashboard / Analytics (Endpoint Bonus)
# ============================================================================

@router.get(
    "/farms/{granja_id}/stats",
    summary="Estadísticas de tareas",
    description=(
            "Obtiene estadísticas agregadas de las tareas de una granja.\n\n"
            "**Métricas incluidas:**\n"
            "- Total de tareas\n"
            "- Conteo por estado (pendiente/en progreso/completada/cancelada)\n"
            "- Conteo por prioridad (baja/media/alta)\n"
            "- Tareas vencidas\n"
            "- Tareas completadas este mes\n\n"
            "**Caso de uso:**\n"
            "- Dashboard principal\n"
            "- Indicadores de gestión\n"
            "- Reportes ejecutivos"
    )
)
def get_farm_task_stats(
        granja_id: int = Path(..., gt=0, description="ID de la granja"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """Estadísticas de tareas de la granja"""
    # Validar que la granja existe
    granja = db.get(Granja, granja_id)
    if not granja:
        raise HTTPException(status_code=404, detail="Granja no encontrada")

    # Validar acceso a la granja
    ensure_user_in_farm_or_admin(
        db, current_user.usuario_id, granja_id, current_user.is_admin_global
    )

    # Obtener todas las tareas de la granja
    todas_tareas = db.query(Tarea).filter(Tarea.granja_id == granja_id).all()

    # Calcular estadísticas
    total = len(todas_tareas)

    por_estado = {
        "p": sum(1 for t in todas_tareas if t.status == "p"),
        "e": sum(1 for t in todas_tareas if t.status == "e"),
        "c": sum(1 for t in todas_tareas if t.status == "c"),
        "x": sum(1 for t in todas_tareas if t.status == "x")
    }

    por_prioridad = {
        "b": sum(1 for t in todas_tareas if t.prioridad == "b"),
        "m": sum(1 for t in todas_tareas if t.prioridad == "m"),
        "a": sum(1 for t in todas_tareas if t.prioridad == "a")
    }

    # Tareas vencidas
    from utils.datetime_utils import today_mazatlan
    hoy = today_mazatlan()
    vencidas = sum(
        1 for t in todas_tareas
        if t.fecha_limite and t.fecha_limite < hoy and t.status not in ["c", "x"]
    )

    # Tareas completadas este mes
    from utils.datetime_utils import now_mazatlan
    ahora = now_mazatlan()
    primer_dia_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    completadas_este_mes = sum(
        1 for t in todas_tareas
        if t.status == "c" and t.updated_at >= primer_dia_mes
    )

    return {
        "total": total,
        "por_estado": por_estado,
        "por_prioridad": por_prioridad,
        "vencidas": vencidas,
        "completadas_este_mes": completadas_este_mes
    }