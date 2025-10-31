# api/cycles.py
"""
Endpoints para gestión de ciclos.
Actualizado con opción de subir archivo de proyección al crear ciclo.
"""

from fastapi import APIRouter, Depends, Query, Path, UploadFile, File, Form
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import ensure_user_in_farm_or_admin
from schemas.cycle import CycleCreate, CycleUpdate, CycleClose, CycleOut, CycleResumenOut
from services.cycle_service import (
    create_cycle, get_active_cycle, list_cycles, get_cycle, update_cycle, close_cycle
)
from services import projection_service
from models.user import Usuario
from models.cycle import Ciclo

router = APIRouter(prefix="/cycles", tags=["Ciclos"])


# ==========================================
# POST - Crear ciclo (CON OPCIÓN DE ARCHIVO)
# ==========================================

@router.post(
    "/farms/{granja_id}",
    response_model=CycleOut,
    status_code=201,
    summary="Crear ciclo (con proyección opcional)",
    description=(
            "Crea un nuevo ciclo para la granja.\n\n"
            "**Archivo opcional (proyección con IA):**\n"
            "- Si envías `file` → procesa con Gemini y crea V1 automáticamente\n"
            "- Si NO envías `file` → solo crea el ciclo (puedes subir proyección después)\n\n"
            "**Auto-setup (si envías archivo):**\n"
            "- Crea plan de siembras automáticamente\n"
            "- Crea olas de cosecha automáticamente\n"
            "- Distribuye fechas uniformemente entre ventanas\n\n"
            "**Restricción:**\n"
            "- Solo 1 ciclo activo por granja\n\n"
            "**Nota sobre fecha_inicio:**\n"
            "- Es la fecha de PRIMERA SIEMBRA PLANIFICADA\n"
            "- Se sincronizará automáticamente con la fecha real al confirmar la última siembra"
    )
)
async def post_cycle(
        granja_id: int = Path(..., gt=0, description="ID de la granja"),
        nombre: str = Form(..., max_length=150, description="Nombre del ciclo"),
        fecha_inicio: str = Form(..., description="Fecha de inicio del ciclo - Primera siembra planificada (YYYY-MM-DD)"),
        fecha_fin_planificada: str | None = Form(None, description="Fecha fin planificada (YYYY-MM-DD)"),
        observaciones: str | None = Form(None, max_length=500, description="Observaciones"),
        file: UploadFile | None = File(None, description="Archivo de proyección (Excel/CSV/PDF) - OPCIONAL"),
        descripcion_proyeccion: str | None = Form(None,
                                                  description="Descripción de la proyección (si se sube archivo)"),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
):
    """
    Crea un ciclo con opción de subir archivo de proyección.

    Si se sube archivo:
    1. Crea el ciclo
    2. Procesa archivo con Gemini
    3. Crea proyección V1 (autopublicada)
    4. Auto-setup de planes si no existen

    Retorna el ciclo + warnings de auto-setup si aplica.
    """
    from datetime import date as date_type
    from fastapi import HTTPException

    ensure_user_in_farm_or_admin(db, user.usuario_id, granja_id, user.is_admin_global)

    # Parsear fechas
    try:
        fecha_inicio_parsed = date_type.fromisoformat(fecha_inicio)
        fecha_fin_parsed = date_type.fromisoformat(fecha_fin_planificada) if fecha_fin_planificada else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Formato de fecha inválido: {e}")

    # Crear payload del ciclo
    payload = CycleCreate(
        nombre=nombre,
        fecha_inicio=fecha_inicio_parsed,
        fecha_fin_planificada=fecha_fin_parsed,
        observaciones=observaciones
    )

    # Crear ciclo
    cycle = create_cycle(db, granja_id, payload)

    # Si hay archivo, procesar proyección
    warnings = []
    if file and file.filename:  # Verificar que el archivo no esté vacío
        try:
            # Validar tipo de archivo
            from services.gemini_service import GeminiService
            GeminiService.validate_file(file)

            proy, proy_warnings = await projection_service.create_projection_from_file(
                db=db,
                ciclo_id=cycle.ciclo_id,
                file=file,
                user_id=user.usuario_id,
                descripcion=descripcion_proyeccion or f"Proyección inicial {cycle.nombre}",
                version="V1",  # Forzar V1
            )
            warnings.extend(proy_warnings)
            warnings.insert(0, f"projection_created: V1 (proyeccion_id={proy.proyeccion_id})")
        except HTTPException:
            # Re-lanzar errores HTTP (422, 415, etc)
            raise
        except Exception as e:
            # Si falla la proyección, no revertir el ciclo creado
            warnings.append(f"projection_error: {str(e)}")

    # Convertir a dict para agregar warnings
    result = CycleOut.model_validate(cycle).model_dump()
    if warnings:
        result["warnings"] = warnings

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
        user: Usuario = Depends(get_current_user)
):
    ensure_user_in_farm_or_admin(db, user.usuario_id, granja_id, user.is_admin_global)
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
        user: Usuario = Depends(get_current_user)
):
    ensure_user_in_farm_or_admin(db, user.usuario_id, granja_id, user.is_admin_global)
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
        user: Usuario = Depends(get_current_user)
):
    cycle = get_cycle(db, ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)
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
        user: Usuario = Depends(get_current_user)
):
    cycle = get_cycle(db, ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)
    return update_cycle(db, ciclo_id, payload)


# ==========================================
# POST - Cerrar ciclo
# ==========================================

@router.post(
    "/{ciclo_id}/close",
    response_model=CycleOut,
    summary="Cerrar ciclo",
    description=(
            "Cierra el ciclo y genera resumen automático.\n\n"
            "**Efectos:**\n"
            "- Cambia status de 'a' → 't' (terminado)\n"
            "- Congela resumen final en `ciclo_resumen`\n"
            "- No se puede revertir"
    )
)
def post_close_cycle(
        ciclo_id: int = Path(..., gt=0),
        payload: CycleClose = ...,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
):
    cycle = get_cycle(db, ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    # TODO: Calcular métricas reales desde biometrías y cosechas
    # Por ahora usamos valores del payload
    return close_cycle(
        db=db,
        ciclo_id=ciclo_id,
        payload=payload,
        sob_final=payload.sob_final_real_pct or 0.0,
        toneladas=payload.toneladas_cosechadas or 0.0,
        n_estanques=payload.n_estanques_cosechados or 0
    )


# ==========================================
# GET - Obtener resumen del ciclo
# ==========================================

@router.get(
    "/{ciclo_id}/resumen",
    response_model=CycleResumenOut | None,
    summary="Obtener resumen del ciclo",
    description="Retorna el resumen (solo si el ciclo está cerrado)"
)
def get_cycle_resumen(
        ciclo_id: int = Path(..., gt=0),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
):
    from models.cycle import CicloResumen

    cycle = get_cycle(db, ciclo_id)
    ensure_user_in_farm_or_admin(db, user.usuario_id, cycle.granja_id, user.is_admin_global)

    if cycle.status != 't':
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="El ciclo no está terminado")

    return db.query(CicloResumen).filter(CicloResumen.ciclo_id == ciclo_id).first()