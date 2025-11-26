"""
Endpoints para gestión de ciclos.
Actualizado con sistema de permisos y sin CicloResumen.
"""
import uuid
from datetime import date as date_type
from fastapi import APIRouter, Depends, Query, Path, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import (
    ensure_user_in_farm_or_admin,
    ensure_user_has_scope,
    Scopes
)
from schemas.cycle import CycleCreate, CycleUpdate, CycleClose, CycleOut
from services.cycle_service import (
    create_cycle, get_active_cycle, list_cycles, get_cycle, update_cycle, close_cycle
)
from services import projection_service
from models.user import Usuario

router = APIRouter(prefix="/cycles", tags=["Ciclos"])


# ==========================================
# POST - Crear ciclo (CON OPCIÓN DE ARCHIVO)
# ==========================================

@router.post(
    "/farms/{granja_id}",
    response_model=dict,  # Retorna dict con ciclo + job_id (opcional)
    status_code=201,
    summary="Crear ciclo (con proyección opcional - ASÍNCRONO)",
    description=(
            "Crea un nuevo ciclo para la granja.\n\n"
            "**Archivo opcional (proyección con IA):**\n"
            "- Si envías `file` → retorna job_id para polling (procesa en background con Celery)\n"
            "- Si NO envías `file` → solo crea el ciclo\n\n"
            "**Polling si envía archivo:**\n"
            "- Consulta GET /jobs/{job_id} cada 2 segundos\n"
            "- Cuando status='completed', proyeccion_id estará disponible\n\n"
            "**Auto-setup (después de completar):**\n"
            "- Crea plan de siembras automáticamente\n"
            "- Crea olas de cosecha automáticamente\n"
            "- Distribuye fechas uniformemente entre ventanas\n\n"
            "**Restricción:**\n"
            "- Solo 1 ciclo activo por granja"
    )
)
async def post_cycle(
        granja_id: int = Path(..., gt=0, description="ID de la granja"),
        nombre: str = Form(..., max_length=150, description="Nombre del ciclo"),
        fecha_inicio: str = Form(..., description="Fecha de inicio del ciclo (YYYY-MM-DD)"),
        fecha_fin_planificada: str | None = Form(None, description="Fecha fin planificada (YYYY-MM-DD)"),
        observaciones: str | None = Form(None, max_length=500, description="Observaciones"),
        file: UploadFile | None = File(None, description="Archivo de proyección (Excel/CSV/PDF) - OPCIONAL"),
        descripcion_proyeccion: str | None = Form(None,
                                                  description="Descripción de la proyección (si se sube archivo)"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Crea un ciclo con opción de subir archivo de proyección (asíncrono).

    Permisos:
    - Admin Global: Puede crear en cualquier granja
    - Admin Granja con gestionar_ciclos: Puede crear en su granja

    Retorna:
    - ciclo (datos del ciclo creado)
    - job_id (si hay archivo) o null (si no hay archivo)
    """
    from services.job_service import create_job
    from workers.tasks import process_projection_file_task

    # 1. Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        granja_id,
        current_user.is_admin_global
    )

    # 2. Validar scope (gestionar_ciclos)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        granja_id,
        Scopes.GESTIONAR_CICLOS,
        current_user.is_admin_global
    )

    # 3. Parsear fechas
    try:
        fecha_inicio_parsed = date_type.fromisoformat(fecha_inicio)
        fecha_fin_parsed = date_type.fromisoformat(fecha_fin_planificada) if fecha_fin_planificada else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Formato de fecha inválido: {e}")

    # 4. Crear payload del ciclo
    payload = CycleCreate(
        nombre=nombre,
        fecha_inicio=fecha_inicio_parsed,
        fecha_fin_planificada=fecha_fin_parsed,
        observaciones=observaciones
    )

    # 5. Crear ciclo (rápido)
    cycle = create_cycle(db, granja_id, payload)

    # 6. Si hay archivo, crear job asíncrono
    job_id = None
    if file and file.filename:
        job_id = str(uuid.uuid4())

        # Leer contenido del archivo
        contents = await file.read()

        # Crear registro de job en BD
        job = create_job(db, job_id, current_user.usuario_id, cycle.ciclo_id)

        # Encolar tarea a Celery (no-bloqueante)
        try:
            process_projection_file_task.delay(
                job_id=job_id,
                ciclo_id=cycle.ciclo_id,
                file_contents=contents,
                file_name=file.filename,
                user_id=current_user.usuario_id,
            )
        except Exception as e:
            job.status = "failed"
            job.error_detail = f"Error al encolar tarea: {str(e)}"
            db.commit()
            # No fallar la creación del ciclo, solo reportar error del job
            pass

    # 7. Retornar ciclo + job_id (si aplica)
    result = CycleOut.model_validate(cycle).model_dump()
    result["job_id"] = job_id

    return result


# ==========================================
# GET - Ciclo activo de granja
# ==========================================

@router.get(
    "/farms/{granja_id}/active",
    response_model=CycleOut | None,
    summary="Obtener ciclo activo",
    description="Retorna el ciclo activo de la granja (si existe)"
)
def get_farm_active_cycle(
    granja_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtener ciclo activo de una granja.

    Lectura implícita: Solo requiere membership en la granja.
    """
    # Solo validar membership (lectura implícita)
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        granja_id,
        current_user.is_admin_global
    )

    return get_active_cycle(db, granja_id)


# ==========================================
# GET - Listar ciclos de granja
# ==========================================

@router.get(
    "/farms/{granja_id}",
    response_model=list[CycleOut],
    summary="Listar ciclos de granja",
    description="Lista todos los ciclos (activos o terminados)"
)
def list_farm_cycles(
    granja_id: int = Path(..., gt=0),
    include_terminated: bool = Query(False, description="Incluir ciclos terminados"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Listar ciclos de una granja.

    Lectura implícita: Solo requiere membership en la granja.
    """
    # Solo validar membership (lectura implícita)
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        granja_id,
        current_user.is_admin_global
    )

    return list_cycles(db, granja_id, include_terminated)


# ==========================================
# GET - Obtener ciclo por ID
# ==========================================

@router.get(
    "/{ciclo_id}",
    response_model=CycleOut,
    summary="Obtener ciclo por ID"
)
def get_cycle_by_id(
    ciclo_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtener un ciclo específico.

    Lectura implícita: Solo requiere membership en la granja del ciclo.
    """
    cycle = get_cycle(db, ciclo_id)

    # Solo validar membership (lectura implícita)
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    return cycle


# ==========================================
# PATCH - Actualizar ciclo
# ==========================================

@router.patch(
    "/{ciclo_id}",
    response_model=CycleOut,
    summary="Actualizar ciclo",
    description="Actualiza datos del ciclo (solo si está activo)"
)
def patch_cycle(
    ciclo_id: int = Path(..., gt=0),
    payload: CycleUpdate = ...,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Actualizar ciclo.

    Permisos:
    - Admin Global: Puede actualizar en cualquier granja
    - Admin Granja con gestionar_ciclos: Puede actualizar en su granja
    """
    cycle = get_cycle(db, ciclo_id)

    # 1. Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    # 2. Validar scope (gestionar_ciclos)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.GESTIONAR_CICLOS,
        current_user.is_admin_global
    )

    # 3. Actualizar ciclo
    return update_cycle(db, ciclo_id, payload)


# ==========================================
# POST - Cerrar ciclo
# ==========================================

@router.post(
    "/{ciclo_id}/close",
    response_model=CycleOut,
    summary="Cerrar ciclo",
    description=(
        "Cierra el ciclo.\n\n"
        "**Efectos:**\n"
        "- Cambia status de 'a' → 'c' (cerrado)\n"
        "- Registra fecha de cierre\n"
        "- Opcionalmente actualiza observaciones\n"
        "- No se puede revertir\n\n"
        "**Nota:** Las métricas (toneladas, sobrevivencia, etc.) se calculan on-demand "
        "desde las tablas operativas (biometrías, cosechas, siembras)."
    )
)
def post_close_cycle(
    ciclo_id: int = Path(..., gt=0),
    payload: CycleClose = ...,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Cerrar ciclo (operación crítica).

    Permisos:
    - Admin Global: Puede cerrar en cualquier granja
    - Admin Granja con cerrar_ciclos: Puede cerrar en su granja

    Nota: cerrar_ciclos está incluido en gestionar_ciclos
    """
    cycle = get_cycle(db, ciclo_id)

    # 1. Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    # 2. Validar scope (cerrar_ciclos - operación crítica)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.CERRAR_CICLOS,
        current_user.is_admin_global
    )

    # 3. Cerrar ciclo
    return close_cycle(db, ciclo_id, payload)