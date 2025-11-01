from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import (
    ensure_user_in_farm_or_admin,
    ensure_user_has_scope,
    Scopes
)
from models.user import Usuario
from models.pond import Estanque
from schemas.pond import PondCreate, PondOut, PondUpdate
from services.pond_service import (
    create_pond, list_ponds_by_farm, get_pond, update_pond, delete_pond
)

router = APIRouter(prefix="/ponds", tags=["ponds"])


@router.post(
    "/farms/{granja_id}",
    response_model=PondOut,
    status_code=201,
    summary="Crear estanque",
    description="Crea un nuevo estanque en la granja. Siempre se crea con status='i' (inactivo)."
)
def create_pond_for_farm(
        granja_id: int,
        payload: PondCreate,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Crear estanque en una granja.

    Permisos:
    - Admin Global: Puede crear en cualquier granja
    - Admin Granja con gestionar_estanques: Puede crear en su granja
    """
    # 1. Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        granja_id,
        current_user.is_admin_global
    )

    # 2. Validar scope (gestionar_estanques)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        granja_id,
        Scopes.GESTIONAR_ESTANQUES,
        current_user.is_admin_global
    )

    # 3. Crear estanque
    return create_pond(db, granja_id, payload)


@router.get(
    "/farms/{granja_id}",
    response_model=list[PondOut],
    summary="Listar estanques de granja",
    description=(
            "Lista estanques de una granja.\n\n"
            "**Query params:**\n"
            "- `vigentes_only=true`: Solo estanques vigentes (útil para operaciones actuales)\n"
            "- `vigentes_only=false` (default): Todos los estanques (incluye histórico)"
    )
)
def list_farm_ponds_endpoint(
        granja_id: int,
        vigentes_only: bool = Query(False, description="Filtrar solo estanques vigentes"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Listar estanques de una granja.

    Lectura implícita: Solo requiere membership en la granja.
    """
    # Solo validar membership (lectura implícita)
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        granja_id,
        current_user.is_admin_global
    )

    return list_ponds_by_farm(db, granja_id, vigentes_only=vigentes_only)


@router.get(
    "/{estanque_id}",
    response_model=PondOut,
    summary="Obtener estanque por ID"
)
def get_pond_by_id(
        estanque_id: int,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Obtener un estanque específico.

    Lectura implícita: Solo requiere membership en la granja del estanque.
    """
    pond = get_pond(db, estanque_id)

    # Solo validar membership (lectura implícita)
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        pond.granja_id,
        current_user.is_admin_global
    )

    return pond


@router.patch(
    "/{estanque_id}",
    response_model=PondOut,
    summary="Actualizar estanque",
    description=(
            "Actualiza un estanque.\n\n"
            "**Cambios simples (nombre, notas):**\n"
            "- Se aplican directamente sin crear nueva versión\n\n"
            "**Cambio de superficie:**\n"
            "- Si el estanque NO tiene historial → actualización directa\n"
            "- Si el estanque tiene historial → requiere confirmación:\n"
            "  1. Primera llamada sin `requires_new_version` → retorna **409** con instrucciones\n"
            "  2. Segunda llamada con `requires_new_version=true` → crea nueva versión:\n"
            "     - Marca estanque actual como `is_vigente=False`\n"
            "     - Crea nuevo estanque con nueva superficie\n"
            "     - Retorna el nuevo estanque\n\n"
            "**Historial se preserva:**\n"
            "- Biometrías, siembras y cosechas siguen vinculadas al estanque original"
    )
)
def patch_pond(
        estanque_id: int,
        payload: PondUpdate,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Actualizar estanque.

    Permisos:
    - Admin Global: Puede actualizar en cualquier granja
    - Admin Granja con gestionar_estanques: Puede actualizar en su granja
    """
    pond = db.get(Estanque, estanque_id)
    if not pond:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Estanque no encontrado")

    # 1. Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        pond.granja_id,
        current_user.is_admin_global
    )

    # 2. Validar scope (gestionar_estanques)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        pond.granja_id,
        Scopes.GESTIONAR_ESTANQUES,
        current_user.is_admin_global
    )

    # 3. Actualizar estanque
    return update_pond(db, estanque_id, payload)


@router.delete(
    "/{estanque_id}",
    summary="Eliminar estanque",
    description=(
            "Elimina un estanque de forma inteligente:\n\n"
            "**Si tiene historial (siembras, biometrías, cosechas):**\n"
            "- Soft delete: marca `is_vigente=False`\n"
            "- Preserva el registro para auditoría\n"
            "- Retorna **200** con metadata\n\n"
            "**Si NO tiene historial:**\n"
            "- Hard delete: elimina físicamente el registro\n"
            "- Retorna **204 No Content**\n\n"
            "Esto protege automáticamente la integridad de datos históricos."
    )
)
def delete_pond_endpoint(
        estanque_id: int,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Eliminar estanque.

    Permisos:
    - Admin Global: Puede eliminar en cualquier granja
    - Admin Granja con gestionar_estanques: Puede eliminar en su granja
    """
    pond = db.get(Estanque, estanque_id)
    if not pond:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Estanque no encontrado")

    # 1. Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        pond.granja_id,
        current_user.is_admin_global
    )

    # 2. Validar scope (gestionar_estanques)
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        pond.granja_id,
        Scopes.GESTIONAR_ESTANQUES,
        current_user.is_admin_global
    )

    # 3. Eliminar estanque
    result = delete_pond(db, estanque_id)

    # Si fue hard delete, retornar 204
    if result.get("deleted"):
        return Response(status_code=204)

    # Si fue soft delete, retornar metadata
    return result