# services/task_service.py
from __future__ import annotations

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from fastapi import HTTPException

from models.task import Tarea, TareaAsignacion
from models.user import Usuario
from schemas.task import TareaCreate, TareaUpdate, TareaUpdateStatus
from utils.datetime_utils import today_mazatlan


# ============================================================================
# Helpers Privados
# ============================================================================

def _validate_user_exists(db: Session, usuario_id: int) -> Usuario:
    """Validar que un usuario existe en la base de datos"""
    user = db.get(Usuario, usuario_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Usuario {usuario_id} no encontrado")
    return user


def _validate_users_exist(db: Session, usuario_ids: list[int]) -> list[Usuario]:
    """Validar que todos los usuarios en la lista existen"""
    if not usuario_ids:
        return []

    users = db.query(Usuario).filter(Usuario.usuario_id.in_(usuario_ids)).all()
    found_ids = {user.usuario_id for user in users}
    missing_ids = set(usuario_ids) - found_ids

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Usuarios no encontrados: {sorted(missing_ids)}"
        )

    return users


def _get_task_responsibles(tarea: Tarea) -> list[int]:
    """
    Obtener lista de usuario_ids responsables.

    Lógica:
    - Si hay asignaciones: retornar todos los asignados
    - Si NO hay asignaciones: retornar [created_by]
    """
    if tarea.asignaciones:
        return [asig.usuario_id for asig in tarea.asignaciones]
    return [tarea.created_by]


def _can_user_complete_task(tarea: Tarea, usuario_id: int) -> bool:
    """
    Verificar si usuario puede completar la tarea.

    Puede si:
    - Está en asignaciones
    - O es creador y NO hay asignaciones
    """
    responsibles = _get_task_responsibles(tarea)
    return usuario_id in responsibles


def _assign_users(db: Session, tarea_id: int, usuario_ids: list[int]) -> None:
    """
    Asignar usuarios a tarea.

    Pasos:
    1. Validar que todos los usuario_ids existan
    2. Crear registros en tarea_asignacion
    3. Manejar duplicados (UNIQUE constraint previene)
    """
    if not usuario_ids:
        return

    # Validar que todos los usuarios existan
    _validate_users_exist(db, usuario_ids)

    # Crear asignaciones
    for usuario_id in usuario_ids:
        asignacion = TareaAsignacion(
            tarea_id=tarea_id,
            usuario_id=usuario_id
        )
        db.add(asignacion)

    db.flush()


def _remove_all_assignments(db: Session, tarea_id: int) -> None:
    """Eliminar todas las asignaciones de una tarea"""
    db.query(TareaAsignacion).filter(
        TareaAsignacion.tarea_id == tarea_id
    ).delete(synchronize_session=False)
    db.flush()


def _get_task_with_relations(db: Session, tarea_id: int) -> Tarea | None:
    """Obtener tarea con todas las relaciones cargadas (evita N+1)"""
    return (
        db.query(Tarea)
        .options(
            joinedload(Tarea.creador),
            joinedload(Tarea.asignaciones).joinedload(TareaAsignacion.usuario),
            joinedload(Tarea.granja),
            joinedload(Tarea.ciclo),
            joinedload(Tarea.estanque)
        )
        .filter(Tarea.tarea_id == tarea_id)
        .first()
    )


# ============================================================================
# CRUD Básico
# ============================================================================

def create_task(db: Session, task_data: TareaCreate, current_user_id: int) -> Tarea:
    """
    Crear nueva tarea.

    Pasos:
    1. Validar que creador existe
    2. Crear registro en tabla tarea (created_by = current_user_id)
    3. Si asignados_ids no está vacío, crear registros en tarea_asignacion
    4. Validar que asignados_ids existan en tabla usuario
    5. Retornar tarea con relationships cargados
    """
    # Validar que el creador existe
    _validate_user_exists(db, current_user_id)

    # Crear tarea
    tarea = Tarea(
        granja_id=task_data.granja_id,
        ciclo_id=task_data.ciclo_id,
        estanque_id=task_data.estanque_id,
        titulo=task_data.titulo,
        descripcion=task_data.descripcion,
        prioridad=task_data.prioridad,
        fecha_limite=task_data.fecha_limite,
        tiempo_estimado_horas=task_data.tiempo_estimado_horas,
        tipo=task_data.tipo,
        es_recurrente=task_data.es_recurrente,
        created_by=current_user_id,
        status="p",
        progreso_pct=0.0
    )
    db.add(tarea)
    db.flush()

    # Asignar usuarios si hay
    if task_data.asignados_ids:
        _assign_users(db, tarea.tarea_id, task_data.asignados_ids)

    db.commit()

    # Retornar con relaciones cargadas
    return _get_task_with_relations(db, tarea.tarea_id)


def get_task(db: Session, tarea_id: int) -> Tarea | None:
    """Obtener tarea por ID con joins de relaciones"""
    return _get_task_with_relations(db, tarea_id)


def update_task(db: Session, tarea_id: int, task_data: TareaUpdate) -> Tarea:
    """
    Actualizar tarea.

    Pasos:
    1. Validar que tarea existe
    2. Actualizar campos básicos de tarea
    3. Si asignados_ids está presente:
       - Eliminar asignaciones actuales
       - Crear nuevas asignaciones
    4. Validar que asignados_ids existan
    5. Retornar tarea actualizada
    """
    tarea = db.get(Tarea, tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Actualizar campos básicos (solo los que no son None)
    update_data = task_data.model_dump(exclude_unset=True, exclude={"asignados_ids"})

    for field, value in update_data.items():
        setattr(tarea, field, value)

    # Lógica automática de status basado en progreso
    if task_data.status == "c":
        # Si status cambia a 'c' (completada), auto-ajustar progreso a 100
        tarea.progreso_pct = 100.0
    elif task_data.progreso_pct is not None:
        # Si se actualiza el progreso, ajustar status automáticamente
        if task_data.progreso_pct >= 100:
            tarea.status = "c"
            tarea.progreso_pct = 100.0
        elif task_data.progreso_pct > 0:
            # Si hay avance pero no está completo, marcar como "en progreso"
            if tarea.status == "p":  # Solo si estaba pendiente
                tarea.status = "e"

    db.add(tarea)
    db.flush()

    # Reasignar usuarios si se especifica
    if task_data.asignados_ids is not None:
        _remove_all_assignments(db, tarea_id)
        if task_data.asignados_ids:  # Solo asignar si la lista no está vacía
            _assign_users(db, tarea_id, task_data.asignados_ids)

    db.commit()

    # Retornar con relaciones cargadas
    return _get_task_with_relations(db, tarea_id)


def update_task_status(db: Session, tarea_id: int, status_data: TareaUpdateStatus) -> Tarea:
    """
    Actualizar solo status y progreso (operación rápida).

    Lógica especial:
    - Si status='c', automáticamente progreso_pct=100
    """
    tarea = db.get(Tarea, tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Actualizar status
    tarea.status = status_data.status

    # Lógica automática basada en status y progreso
    if status_data.status == "c":
        # Si se marca como completada, forzar progreso a 100
        tarea.progreso_pct = 100.0
    elif status_data.progreso_pct is not None:
        # Si se actualiza progreso, validar consistencia con status
        if status_data.progreso_pct >= 100:
            tarea.status = "c"
            tarea.progreso_pct = 100.0
        elif status_data.progreso_pct > 0:
            # Si hay avance y status es 'p', cambiar a 'e'
            if status_data.status == "p":
                tarea.status = "e"
            tarea.progreso_pct = status_data.progreso_pct
        else:
            # progreso_pct == 0
            tarea.progreso_pct = status_data.progreso_pct

    db.add(tarea)
    db.commit()

    # Retornar con relaciones cargadas
    return _get_task_with_relations(db, tarea_id)


def delete_task(db: Session, tarea_id: int) -> None:
    """
    Eliminar tarea.
    CASCADE automático eliminará asignaciones.
    """
    tarea = db.get(Tarea, tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    db.delete(tarea)
    db.commit()


def duplicate_task(db: Session, tarea_id: int, current_user_id: int) -> Tarea:
    """
    Duplicar tarea (útil para recurrentes).

    Copia:
    - titulo, descripcion, tipo, prioridad, tiempo_estimado_horas, es_recurrente
    - granja_id, ciclo_id, estanque_id
    - asignaciones (mismos usuarios)

    NO copia:
    - fecha_limite (null)
    - progreso_pct (0)
    - status (siempre 'p')
    - created_at (nueva fecha)
    """
    # Obtener tarea original con asignaciones
    original = _get_task_with_relations(db, tarea_id)
    if not original:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Crear nueva tarea (copia)
    nueva_tarea = Tarea(
        granja_id=original.granja_id,
        ciclo_id=original.ciclo_id,
        estanque_id=original.estanque_id,
        titulo=original.titulo,
        descripcion=original.descripcion,
        prioridad=original.prioridad,
        tipo=original.tipo,
        tiempo_estimado_horas=original.tiempo_estimado_horas,
        es_recurrente=original.es_recurrente,
        created_by=current_user_id,
        status="p",
        progreso_pct=0.0,
        fecha_limite=None  # No copiar fecha límite
    )
    db.add(nueva_tarea)
    db.flush()

    # Copiar asignaciones
    if original.asignaciones:
        asignados_ids = [asig.usuario_id for asig in original.asignaciones]
        _assign_users(db, nueva_tarea.tarea_id, asignados_ids)

    db.commit()

    # Retornar con relaciones cargadas
    return _get_task_with_relations(db, nueva_tarea.tarea_id)


# ============================================================================
# Queries de Filtrado
# ============================================================================

def get_tasks_by_farm(
        db: Session,
        granja_id: int,
        status: str | None = None,
        asignado_a: int | None = None,
        ciclo_id: int | None = None,
        skip: int = 0,
        limit: int = 100
) -> list[Tarea]:
    """
    Listar tareas de una granja con filtros opcionales.

    Filtros:
    - status: filtrar por estado
    - asignado_a: tareas donde usuario_id está asignado O es creador
    - ciclo_id: tareas de un ciclo específico
    """
    query = (
        db.query(Tarea)
        .options(
            joinedload(Tarea.creador),
            joinedload(Tarea.asignaciones).joinedload(TareaAsignacion.usuario)
        )
        .filter(Tarea.granja_id == granja_id)
    )

    # Filtro por status
    if status:
        query = query.filter(Tarea.status == status)

    # Filtro por ciclo
    if ciclo_id:
        query = query.filter(Tarea.ciclo_id == ciclo_id)

    # Filtro por usuario asignado O creador
    if asignado_a:
        query = query.filter(
            or_(
                Tarea.created_by == asignado_a,
                Tarea.asignaciones.any(TareaAsignacion.usuario_id == asignado_a)
            )
        )

    return query.order_by(Tarea.created_at.desc()).offset(skip).limit(limit).all()


def get_user_tasks(
        db: Session,
        usuario_id: int,
        granja_id: int | None = None,
        status: str | None = None,
        include_created: bool = True,
        skip: int = 0,
        limit: int = 100
) -> list[Tarea]:
    """
    Obtener tareas de un usuario.

    Lógica:
    - Tareas donde está asignado (JOIN con tarea_asignacion)
    - Si include_created=True, también tareas que creó sin asignaciones
    """
    query = db.query(Tarea).options(
        joinedload(Tarea.creador),
        joinedload(Tarea.asignaciones).joinedload(TareaAsignacion.usuario)
    )

    # Condiciones base
    conditions = []

    # Tareas asignadas
    conditions.append(Tarea.asignaciones.any(TareaAsignacion.usuario_id == usuario_id))

    # Tareas creadas sin asignaciones (si include_created=True)
    if include_created:
        conditions.append(
            and_(
                Tarea.created_by == usuario_id,
                ~Tarea.asignaciones.any()
            )
        )

    query = query.filter(or_(*conditions))

    # Filtro por granja
    if granja_id:
        query = query.filter(Tarea.granja_id == granja_id)

    # Filtro por status
    if status:
        query = query.filter(Tarea.status == status)

    return query.order_by(Tarea.created_at.desc()).offset(skip).limit(limit).all()


def get_overdue_tasks(db: Session, granja_id: int) -> list[Tarea]:
    """
    Tareas vencidas (fecha_limite < HOY y status != 'c' y status != 'x').
    Ordenar por fecha_limite ASC.
    """
    hoy = today_mazatlan()

    return (
        db.query(Tarea)
        .options(
            joinedload(Tarea.creador),
            joinedload(Tarea.asignaciones).joinedload(TareaAsignacion.usuario)
        )
        .filter(
            Tarea.granja_id == granja_id,
            Tarea.fecha_limite < hoy,
            Tarea.status.notin_(["c", "x"])
        )
        .order_by(Tarea.fecha_limite.asc())
        .all()
    )