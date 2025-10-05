from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from models.granja import Granja
from models.ciclo import Ciclo
from models.usuario import Usuario
from models.usuario_granja import UsuarioGranja
from utils.permissions import is_user_associated_to_granja
from enums.roles import Role


# ========= Helpers de roles / visibilidad =========

def _user_has_any_role(user: Usuario, roles: List[Role]) -> bool:
    """
    Soporta:
      - user.roles = [Rol] con atributo .nombre
      - user.roles = [UsuarioRol] con relación .rol.nombre
    """
    if not getattr(user, "roles", None):
        return False

    objetivos = {r.value for r in roles}
    for r in user.roles:
        nombre = getattr(r, "nombre", None)  # caso relación directa a Rol
        if nombre is None:
            rol_rel = getattr(r, "rol", None)  # caso pivote UsuarioRol.rol
            nombre = getattr(rol_rel, "nombre", None)
        if nombre in objetivos:
            return True
    return False


def _query_visible_granjas(db: Session, user: Usuario):
    """
    - admin_global ve todas las granjas
    - resto: solo granjas asociadas al usuario
    """
    if _user_has_any_role(user, [Role.admin_global]):
        return db.query(Granja)

    return (
        db.query(Granja)
        .join(UsuarioGranja, UsuarioGranja.granja_id == Granja.granja_id)
        .filter(UsuarioGranja.usuario_id == user.usuario_id)
    )


# ========= Selectores y filtros =========

def list_granjas(
    db: Session,
    user: Usuario,
    q: Optional[str],
    page: int,
    page_size: int,
    order_by: str,
    order: str,
) -> Tuple[List[Granja], int]:
    query = _query_visible_granjas(db, user)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (Granja.nombre.ilike(like)) | (Granja.ubicacion.ilike(like))
        )

    # Orden
    valid_order = {"nombre": Granja.nombre, "created_at": Granja.created_at}
    col = valid_order.get(order_by, Granja.created_at)
    query = query.order_by(col.asc() if order == "asc" else col.desc())

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def get_granja_visible(db: Session, user: Usuario, granja_id: int) -> Granja:
    """
    Devuelve la granja si el usuario tiene visibilidad sobre ella.
    - admin_global: acceso total
    - resto: debe estar asociado a la granja
    """
    if not _user_has_any_role(user, [Role.admin_global]):
        if not is_user_associated_to_granja(db, user.usuario_id, granja_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="granja_not_found: No existe o no tienes acceso."
            )

    obj = db.query(Granja).filter(Granja.granja_id == granja_id).first()
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="granja_not_found: No existe o no tienes acceso."
        )
    return obj


# ========= Mutaciones =========

def create_granja(db: Session, user: Usuario, data: Dict) -> Granja:
    # Unicidad por nombre (a nivel global)
    nombre = (data.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="nombre_required: El nombre es requerido."
        )

    exists = (
        db.query(Granja)
        .filter(func.lower(Granja.nombre) == nombre.lower())
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="granja_name_duplicated: Ya existe una granja con ese nombre."
        )

    obj = Granja(**data)
    obj.created_by = user.usuario_id
    db.add(obj)
    db.flush()  # obtener granja_id

    # Política: auto-asociar al creador si no es admin_global
    if not _user_has_any_role(user, [Role.admin_global]):
        db.add(UsuarioGranja(usuario_id=user.usuario_id, granja_id=obj.granja_id))

    db.commit()
    db.refresh(obj)
    return obj


def update_granja(db: Session, user: Usuario, granja_id: int, changes: Dict) -> Granja:
    obj = get_granja_visible(db, user, granja_id)

    # Validar unicidad si cambia el nombre
    new_nombre = changes.get("nombre")
    if new_nombre:
        new_nombre_norm = new_nombre.strip()
        if new_nombre_norm and new_nombre_norm.lower() != (obj.nombre or "").strip().lower():
            dup = (
                db.query(Granja)
                .filter(func.lower(Granja.nombre) == new_nombre_norm.lower())
                .first()
            )
            if dup:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="granja_name_duplicated: Ya existe una granja con ese nombre."
                )

    for k, v in changes.items():
        setattr(obj, k, v)

    obj.updated_by = user.usuario_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def delete_granja(db: Session, user: Usuario, granja_id: int) -> None:
    obj = get_granja_visible(db, user, granja_id)

    # Evitar borrar si hay ciclos relacionados
    ciclo_existente = db.query(Ciclo).filter(Ciclo.granja_id == granja_id).first()
    if ciclo_existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="granja_in_use: La granja tiene ciclos relacionados y no puede eliminarse."
        )

    db.delete(obj)
    db.commit()


# ========= Asociación de usuarios =========

def sync_usuarios_granja(
    db: Session,
    user: Usuario,
    granja_id: int,
    add_ids: Optional[List[int]],
    remove_ids: Optional[List[int]],
) -> dict:
    # Debe existir y ser visible
    _ = get_granja_visible(db, user, granja_id)

    # Si NO es admin_global, debe ser admin_granja asociado
    if not _user_has_any_role(user, [Role.admin_global]):
        if not _user_has_any_role(user, [Role.admin_granja]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden_role")
        if not is_user_associated_to_granja(db, user.usuario_id, granja_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="granja_not_found")

    add_ids = list(set(add_ids or []))
    remove_ids = list(set(remove_ids or []))

    # Agregar
    added = 0
    for uid in add_ids:
        exists = (
            db.query(UsuarioGranja)
            .filter(
                UsuarioGranja.usuario_id == uid,
                UsuarioGranja.granja_id == granja_id
            )
            .first()
        )
        if not exists:
            db.add(UsuarioGranja(usuario_id=uid, granja_id=granja_id))
            added += 1

    # Quitar
    removed = 0
    if remove_ids:
        removed = (
            db.query(UsuarioGranja)
            .filter(
                UsuarioGranja.granja_id == granja_id,
                UsuarioGranja.usuario_id.in_(remove_ids),
            )
            .delete(synchronize_session=False)
        )

    db.commit()
    return {"added": added, "removed": removed}
