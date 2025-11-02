"""
Router para gestión de proyecciones con Gemini AI
Migrado con sistema completo de permisos
"""

from typing import List
from fastapi import APIRouter, Depends, Path, Query, UploadFile, File, status, HTTPException
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
from schemas.projection import (
    ProyeccionUpdate,
    ProyeccionOut,
    ProyeccionDetailOut,
    ProyeccionPublish
)
from services import projection_service

router = APIRouter(prefix="/projections", tags=["projections"])


# ==========================================
# Helpers
# ==========================================

def _ensure_user_access_to_cycle(db: Session, current_user: Usuario, ciclo_id: int):
    """Valida que el usuario tenga acceso al ciclo"""
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )
    return cycle


# ==========================================
# POST - Crear proyección desde archivo (Gemini)
# ==========================================

@router.post(
    "/cycles/{ciclo_id}/from-file",
    response_model=ProyeccionDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear proyección desde archivo con IA",
    description=(
            "Procesa un archivo (Excel, CSV, PDF o imagen) con Google Gemini para extraer automáticamente "
            "las líneas de proyección.\n\n"
            "**Tipos de archivo soportados:**\n"
            "- Excel: `.xlsx`, `.xls`\n"
            "- CSV: `.csv`\n"
            "- PDF: `.pdf`\n"
            "- Imágenes: `.png`, `.jpg`, `.jpeg`\n\n"
            "**Auto-setup condicional:**\n"
            "- Si NO existe plan de siembras O está en estado 'p' → crea/actualiza plan automáticamente\n"
            "- Si NO existen olas de cosecha O están en estado 'p' → crea olas automáticamente\n"
            "- Si ya hay planes en ejecución ('e') o finalizados ('f') → solo crea proyección (para comparación)\n\n"
            "**Reglas de versionamiento:**\n"
            "- Solo se permite 1 borrador por ciclo\n"
            "- **V1 se autopublica inmediatamente**\n"
            "- Versiones posteriores quedan en borrador"
    )
)
async def create_projection_from_file(
        ciclo_id: int = Path(..., gt=0, description="ID del ciclo"),
        file: UploadFile = File(..., description="Archivo a procesar (Excel, CSV, PDF, imagen)"),
        version: str | None = Query(
            None,
            max_length=20,
            description="Versión (opcional, se autodetecta si no se proporciona)"
        ),
        descripcion: str | None = Query(None, max_length=255, description="Descripción opcional"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Crea una proyección procesando un archivo con Gemini.

    Permisos:
    - Admin Global: Puede crear en cualquier granja
    - Admin Granja o Biólogo con gestionar_proyecciones: Puede crear en su granja

    Retorna:
    - proyeccion_id
    - version
    - status (p=publicada si es V1, b=borrador si es V2+)
    - warnings con información del auto-setup
    """
    cycle = _ensure_user_access_to_cycle(db, current_user, ciclo_id)

    # Validar scope (gestionar_proyecciones)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.GESTIONAR_PROYECCIONES,
        current_user.is_admin_global
    )

    proyeccion, warnings = await projection_service.create_projection_from_file(
        db=db,
        ciclo_id=ciclo_id,
        file=file,
        user_id=current_user.usuario_id,
        descripcion=descripcion,
        version=version,
    )

    # Agregar warnings a la respuesta
    result = ProyeccionDetailOut.model_validate(proyeccion)

    return {
        **result.model_dump(),
        "warnings": warnings
    }


# ==========================================
# GET - Listar proyecciones de un ciclo
# ==========================================

@router.get(
    "/cycles/{ciclo_id}",
    response_model=List[ProyeccionOut],
    summary="Listar proyecciones de un ciclo",
    description="Obtiene todas las proyecciones de un ciclo (sin líneas semanales)"
)
def list_projections(
        ciclo_id: int = Path(..., gt=0),
        include_cancelled: bool = Query(False, description="Incluir proyecciones canceladas"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Listar proyecciones de un ciclo.

    Permisos:
    - Admin Global: Puede ver en cualquier granja
    - Usuarios con ver_proyecciones: Pueden ver en su granja

    IMPORTANTE: Operador NO puede ver proyecciones (no tiene el scope)
    """
    cycle = _ensure_user_access_to_cycle(db, current_user, ciclo_id)

    # Validar scope (ver_proyecciones) - Lectura restringida
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.VER_PROYECCIONES,
        current_user.is_admin_global
    )

    return projection_service.list_projections(db, ciclo_id, include_cancelled)


# ==========================================
# GET - Obtener proyección actual
# ==========================================

@router.get(
    "/cycles/{ciclo_id}/current",
    response_model=ProyeccionDetailOut | None,
    summary="Obtener proyección actual (publicada)",
    description="Retorna la proyección marcada como actual (is_current=True)"
)
def get_current_projection(
        ciclo_id: int = Path(..., gt=0),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Obtener proyección actual del ciclo.

    Permisos:
    - Admin Global: Puede ver en cualquier granja
    - Usuarios con ver_proyecciones: Pueden ver en su granja
    """
    cycle = _ensure_user_access_to_cycle(db, current_user, ciclo_id)

    # Validar scope (ver_proyecciones) - Lectura restringida
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.VER_PROYECCIONES,
        current_user.is_admin_global
    )

    return projection_service.get_current_projection(db, ciclo_id)


# ==========================================
# GET - Obtener borrador
# ==========================================

@router.get(
    "/cycles/{ciclo_id}/draft",
    response_model=ProyeccionDetailOut | None,
    summary="Obtener borrador actual",
    description="Retorna el borrador (status='b') si existe"
)
def get_draft_projection(
        ciclo_id: int = Path(..., gt=0),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Obtener borrador actual del ciclo.

    Permisos:
    - Admin Global: Puede ver en cualquier granja
    - Usuarios con ver_proyecciones: Pueden ver en su granja
    """
    cycle = _ensure_user_access_to_cycle(db, current_user, ciclo_id)

    # Validar scope (ver_proyecciones) - Lectura restringida
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.VER_PROYECCIONES,
        current_user.is_admin_global
    )

    return projection_service.get_draft_projection(db, ciclo_id)


# ==========================================
# GET - Obtener proyección específica con líneas
# ==========================================

@router.get(
    "/{proyeccion_id}",
    response_model=ProyeccionDetailOut,
    summary="Obtener proyección completa",
    description="Retorna una proyección con todas sus líneas semanales"
)
def get_projection_detail(
        proyeccion_id: int = Path(..., gt=0),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Obtener proyección específica con líneas.

    Permisos:
    - Admin Global: Puede ver en cualquier granja
    - Usuarios con ver_proyecciones: Pueden ver en su granja
    """
    proj = projection_service.get_projection_with_lines(db, proyeccion_id)

    cycle = db.get(Ciclo, proj.ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    # Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    # Validar scope (ver_proyecciones) - Lectura restringida
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.VER_PROYECCIONES,
        current_user.is_admin_global
    )

    return proj


# ==========================================
# PATCH - Actualizar metadatos de proyección
# ==========================================

@router.patch(
    "/{proyeccion_id}",
    response_model=ProyeccionOut,
    summary="Actualizar metadatos de proyección",
    description="Actualiza descripción y parámetros objetivo. Solo permitido en borradores."
)
def update_projection(
        proyeccion_id: int = Path(..., gt=0),
        payload: ProyeccionUpdate = ...,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Actualizar metadatos de proyección.

    Permisos:
    - Admin Global: Puede actualizar en cualquier granja
    - Admin Granja o Biólogo con gestionar_proyecciones: Puede actualizar en su granja
    """
    proj = projection_service._get_projection(db, proyeccion_id)

    cycle = db.get(Ciclo, proj.ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    # Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    # Validar scope (gestionar_proyecciones)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.GESTIONAR_PROYECCIONES,
        current_user.is_admin_global
    )

    return projection_service.update_projection(db, proyeccion_id, payload)


# ==========================================
# POST - Publicar proyección
# ==========================================

@router.post(
    "/{proyeccion_id}/publish",
    response_model=ProyeccionOut,
    summary="Publicar proyección",
    description=(
            "Publica una proyección en borrador.\n\n"
            "**Efectos:**\n"
            "- Cambia status de 'b' → 'p'\n"
            "- Marca is_current=True\n"
            "- Desmarca la proyección anterior como actual\n"
            "- Congela la versión (no se puede editar más)"
    )
)
def publish_projection(
        proyeccion_id: int = Path(..., gt=0),
        payload: ProyeccionPublish = ...,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Publicar proyección (operación crítica).

    Permisos:
    - Admin Global: Puede publicar en cualquier granja
    - Admin Granja o Biólogo con gestionar_proyecciones: Puede publicar en su granja
    """
    proj = projection_service._get_projection(db, proyeccion_id)

    cycle = db.get(Ciclo, proj.ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    # Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    # Validar scope (gestionar_proyecciones)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.GESTIONAR_PROYECCIONES,
        current_user.is_admin_global
    )

    return projection_service.publish_projection(db, proyeccion_id)


# ==========================================
# DELETE - Cancelar proyección
# ==========================================

@router.delete(
    "/{proyeccion_id}",
    response_model=ProyeccionOut,
    summary="Cancelar proyección",
    description=(
            "Cancela una proyección (status → 'x').\n\n"
            "**Restricción:**\n"
            "- No se puede cancelar la proyección actual (is_current=True)"
    )
)
def cancel_projection(
        proyeccion_id: int = Path(..., gt=0),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Cancelar proyección.

    Permisos:
    - Admin Global: Puede cancelar en cualquier granja
    - Admin Granja o Biólogo con gestionar_proyecciones: Puede cancelar en su granja
    """
    proj = projection_service._get_projection(db, proyeccion_id)

    cycle = db.get(Ciclo, proj.ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    # Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        current_user.is_admin_global
    )

    # Validar scope (gestionar_proyecciones)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        cycle.granja_id,
        Scopes.GESTIONAR_PROYECCIONES,
        current_user.is_admin_global
    )

    return projection_service.cancel_projection(db, proyeccion_id)