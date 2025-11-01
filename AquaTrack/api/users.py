from fastapi import APIRouter, Depends, Query
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
    UserFarmOut,
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

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def get_users(
    granja_id: int | None = Query(None, description="Filtrar por granja"),
    status: str | None = Query(None, description="Filtrar por status (a/i)"),
    search: str | None = Query(None, description="Buscar por nombre, username, email"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Listar usuarios con filtros (admin o gestor de usuarios)"""
    if not user.is_admin_global:
        from fastapi import HTTPException, status as http_status

        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Solo admin global puede listar usuarios",
        )
    return list_users(db, granja_id=granja_id, status_filter=status, search=search)


@router.get("/{usuario_id}", response_model=UserOut)
def get_user_by_id(
    usuario_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Ver perfil de usuario (propio o admin)"""
    if not user.is_admin_global and user.usuario_id != usuario_id:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo admin global puede eliminar usuarios permanentemente",
        )
    return hard_delete_user(db, usuario_id)


@router.post("/{usuario_id}/farms")
def post_user_farm(
    usuario_id: int,
    payload: AssignUserToFarmIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Asignar usuario a granja con rol"""
    if not user.is_admin_global:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo admin global puede asignar usuarios a granjas",
        )
    return assign_user_to_farm(db, usuario_id, payload)


@router.delete("/{usuario_id}/farms/{granja_id}")
def delete_user_farm(
    usuario_id: int,
    granja_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Quitar usuario de granja"""
    if not user.is_admin_global:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo admin global puede quitar usuarios de granjas",
        )
    return remove_user_from_farm(db, usuario_id, granja_id)


@router.patch("/{usuario_id}/farms/{granja_id}")
def patch_user_farm_role(
    usuario_id: int,
    granja_id: int,
    payload: UpdateUserFarmRoleIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Cambiar rol de usuario en granja"""
    if not user.is_admin_global:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo admin global puede cambiar roles",
        )
    return update_user_farm_role(db, usuario_id, granja_id, payload)


@router.get("/{usuario_id}/farms", response_model=list[UserFarmOut])
def get_user_farms_list(
    usuario_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Ver granjas del usuario"""
    if not user.is_admin_global and user.usuario_id != usuario_id:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver las granjas de este usuario",
        )
    return get_user_farms(db, usuario_id)