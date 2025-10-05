# utils/permissions.py
from typing import Iterable, List, Union
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from enums.roles import Role
from models.usuario import Usuario
from models.usuario_granja import UsuarioGranja


def _extract_role_name(role_obj) -> Union[str, None]:
    """
    Intenta extraer el nombre del rol desde:
      - Rol(nombre=...)
      - UsuarioRol(rol=Rol(nombre=...))
    Devuelve el nombre (str) o None si no se pudo.
    """
    # Caso relación directa a Rol
    nombre = getattr(role_obj, "nombre", None)
    if nombre is not None:
        return nombre

    # Caso pivote UsuarioRol -> .rol.nombre
    rel = getattr(role_obj, "rol", None)
    if rel is not None:
        return getattr(rel, "nombre", None)

    return None


def user_has_any_role(user: Usuario, roles: Iterable[Union[Role, str]]) -> bool:
    """
    Devuelve True si el usuario tiene al menos uno de los roles en 'roles'.
    'roles' puede contener enums Role o strings.
    """
    if not getattr(user, "roles", None):
        return False

    objetivo = {
        (r.value if isinstance(r, Role) else str(r))
        for r in roles
    }

    for r in user.roles:
        nombre = _extract_role_name(r)
        if nombre and nombre in objetivo:
            return True
    return False


def ensure_roles(user: Usuario, roles: List[Union[Role, str]]) -> None:
    """
    Lanza 403 si el usuario no tiene alguno de los roles requeridos.
    """
    if not user_has_any_role(user, roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden_role"
        )


def is_user_associated_to_granja(db: Session, usuario_id: int, granja_id: int) -> bool:
    """
    Verifica si el usuario está asociado a la granja vía tabla pivote UsuarioGranja.
    """
    return db.query(UsuarioGranja).filter(
        UsuarioGranja.usuario_id == usuario_id,
        UsuarioGranja.granja_id == granja_id
    ).first() is not None


def ensure_visibility_granja(db: Session, user: Usuario, granja_id: int) -> None:
    """
    Lanza 404 si el usuario no tiene visibilidad sobre la granja (a menos que sea admin_global).
    """
    if user_has_any_role(user, [Role.admin_global]):
        return
    if not is_user_associated_to_granja(db, user.usuario_id, granja_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="granja_not_found: No existe o no tienes acceso."
        )
