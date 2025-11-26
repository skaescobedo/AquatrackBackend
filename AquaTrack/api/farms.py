from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import (
    ensure_user_in_farm_or_admin,
    ensure_user_has_scope,
    Scopes
)
from schemas.farm import FarmCreate, FarmOut, FarmUpdate
from services.farm_service import list_farms, create_farm, update_farm, get_farm
from models.user import Usuario

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("", response_model=list[FarmOut])
def get_farms(
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Listar granjas según permisos del usuario.

    - Admin Global: Ve todas las granjas
    - Usuario normal: Ve solo las granjas donde tiene membership activo

    NO requiere scope específico, solo membership.
    """
    return list_farms(db, current_user)


@router.post("", response_model=FarmOut)
def post_farm(
        payload: FarmCreate,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Crear una nueva granja.

    Solo Admin Global puede crear granjas.
    """
    if not current_user.is_admin_global:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo Admin Global puede crear granjas"
        )

    return create_farm(db, payload)


@router.put("/{granja_id}", response_model=FarmOut)
def put_farm(
        granja_id: int,
        payload: FarmUpdate,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Actualizar una granja existente.

    Permisos:
    - Admin Global: Puede actualizar cualquier granja
    - Admin Granja con gestionar_estanques: Puede actualizar su granja

    Razón: Actualizar granja (nombre, ubicación, superficie) es parte de
    la gestión de infraestructura.
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

    # 3. Actualizar
    return update_farm(db, granja_id, payload)


@router.get("/{granja_id}", response_model=FarmOut)
def get_farm_by_id(
        granja_id: int,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user)
):
    """
    Obtener una granja específica por ID.

    Permisos:
    - Admin Global: Puede ver cualquier granja
    - Usuario normal: Puede ver solo granjas donde tiene membership activo

    NO requiere scope específico, solo membership.
    """
    # Obtener la granja
    farm = get_farm(db, granja_id)

    # Validar que el usuario tiene acceso a esta granja
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        granja_id,
        current_user.is_admin_global
    )

    return farm