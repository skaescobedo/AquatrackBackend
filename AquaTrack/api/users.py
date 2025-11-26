from fastapi import APIRouter, Depends, Query, HTTPException, status as http_status
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from models.user import Usuario
from schemas.user import (
    UserCreateAdmin,
    UserOut,
    UserUpdate,
    ChangePasswordIn,
    AssignUserToFarmIn,
    UpdateUserFarmRoleIn,
    UserFarmOut, UserListItem,
)
from services.user_service import (
    list_users,
    get_user,
    create_user,
    update_user,
    change_password,
    soft_delete_user,
    hard_delete_user,
    assign_user_to_farm,
    remove_user_from_farm,
    update_user_farm_role,
    get_user_farms,
)
from utils.permissions import (
    ensure_user_in_farm_or_admin,
    ensure_can_manage_users,
    get_user_farms_with_scope,
    Scopes,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserListItem])
def get_users(
        granja_id: int | None = Query(None, description="Filtrar por granja"),
        status: str | None = Query(None, description="Filtrar por status (a/i)"),
        search: str | None = Query(None, description="Buscar por nombre, username, email"),
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Listar usuarios con filtros.

    Permisos:
    - Admin Global: Ve TODOS los usuarios del sistema
    - Usuarios con ver_usuarios_granja: Ven usuarios de SUS granjas
    - Usuarios con gestionar_usuarios_granja: Ven usuarios de SUS granjas
    """
    if current_user.is_admin_global:
        # Admin Global ve todos los usuarios
        return list_users(db, None, granja_id, status, search)

    # Obtener granjas donde tiene ver_usuarios_granja O gestionar_usuarios_granja
    granja_ids = get_user_farms_with_scope(
        db,
        current_user.usuario_id,
        [Scopes.VER_USUARIOS_GRANJA, Scopes.GESTIONAR_USUARIOS_GRANJA],
        current_user.is_admin_global
    )

    if not granja_ids:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para ver usuarios",
        )

    # Si filtra por granja_id específica, validar que tenga permiso
    if granja_id is not None and granja_id not in granja_ids:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos en esta granja",
        )

    return list_users(db, granja_ids, granja_id, status, search)


@router.get("/{usuario_id}", response_model=UserOut)
def get_user_by_id(
        usuario_id: int,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """Ver perfil de usuario (propio o admin)"""
    if not user.is_admin_global and user.usuario_id != usuario_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver este perfil",
        )
    return get_user(db, usuario_id)


@router.post("", response_model=UserOut)
def post_user(
        payload: UserCreateAdmin,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """Crear usuario (admin o gestor de usuarios)"""
    if not user.is_admin_global:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Solo admin global puede crear usuarios",
        )
    return create_user(db, payload)


@router.patch("/{usuario_id}", response_model=UserOut)
def patch_user(
        usuario_id: int,
        payload: UserUpdate,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """Editar perfil (propio o admin)"""
    if not user.is_admin_global and user.usuario_id != usuario_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para editar este perfil",
        )
    return update_user(db, usuario_id, payload)


@router.patch("/{usuario_id}/password", response_model=UserOut)
def patch_user_password(
        usuario_id: int,
        payload: ChangePasswordIn,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """Cambiar contraseña (requiere contraseña actual)"""
    if user.usuario_id != usuario_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Solo puedes cambiar tu propia contraseña",
        )
    return change_password(db, usuario_id, payload)


@router.delete("/{usuario_id}", response_model=UserOut)
def delete_user_soft(
        usuario_id: int,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """Desactivar usuario (soft delete)"""
    if not user.is_admin_global:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Solo admin global puede desactivar usuarios",
        )
    return soft_delete_user(db, usuario_id)


@router.delete("/{usuario_id}/hard")
def delete_user_hard(
        usuario_id: int,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """Eliminar usuario permanentemente (solo admin global)"""
    if not user.is_admin_global:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Solo admin global puede eliminar usuarios permanentemente",
        )
    return hard_delete_user(db, usuario_id)


@router.post("/{usuario_id}/farms")
def post_user_farm(
        usuario_id: int,
        payload: AssignUserToFarmIn,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Asignar usuario a granja con rol.

    Permisos:
    - Admin Global: Puede asignar a cualquier granja + agregar scopes adicionales
    - Usuarios con gestionar_usuarios_granja: Pueden asignar solo en sus granjas
    """
    # 1. Validar membership (pertenece a la granja)
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        payload.granja_id,
        current_user.is_admin_global,
    )

    # 2. Validar scope gestionar_usuarios_granja
    ensure_can_manage_users(db, current_user, payload.granja_id)

    # 3. Solo Admin Global puede agregar scopes adicionales
    if payload.additional_scopes and not current_user.is_admin_global:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Solo Admin Global puede asignar scopes adicionales",
        )

    return assign_user_to_farm(db, usuario_id, payload)


@router.delete("/{usuario_id}/farms/{granja_id}")
def delete_user_farm(
        usuario_id: int,
        granja_id: int,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Quitar usuario de granja.

    Permisos:
    - Admin Global: Puede remover de cualquier granja
    - Usuarios con gestionar_usuarios_granja: Pueden remover solo en sus granjas
    """
    # 1. Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        granja_id,
        current_user.is_admin_global,
    )

    # 2. Validar scope gestionar_usuarios_granja
    ensure_can_manage_users(db, current_user, granja_id)

    return remove_user_from_farm(db, usuario_id, granja_id)


@router.patch("/{usuario_id}/farms/{granja_id}")
def patch_user_farm_role(
        usuario_id: int,
        granja_id: int,
        payload: UpdateUserFarmRoleIn,
        db: Session = Depends(get_db),
        current_user: Usuario = Depends(get_current_user),
):
    """
    Cambiar rol de usuario en granja.

    IMPORTANTE: Al cambiar rol, se RESETEAN los scopes a los por defecto del nuevo rol.

    Permisos:
    - Admin Global: Puede cambiar roles en cualquier granja
    - Usuarios con gestionar_usuarios_granja: Pueden cambiar roles solo en sus granjas
    """
    # 1. Validar membership
    ensure_user_in_farm_or_admin(
        db,
        current_user.usuario_id,
        granja_id,
        current_user.is_admin_global,
    )

    # 2. Validar scope gestionar_usuarios_granja
    ensure_can_manage_users(db, current_user, granja_id)

    return update_user_farm_role(db, usuario_id, granja_id, payload)


@router.get("/{usuario_id}/farms", response_model=list[UserFarmOut])
def get_user_farms_list(
        usuario_id: int,
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user),
):
    """Ver granjas del usuario"""
    if not user.is_admin_global and user.usuario_id != usuario_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver las granjas de este usuario",
        )
    return get_user_farms(db, usuario_id)