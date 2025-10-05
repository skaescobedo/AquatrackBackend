from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.usuario import Usuario
from models.granja import Granja
from models.estanque import Estanque
from models.siembra_estanque import SiembraEstanque  # si existe
from models.biometria import Biometria               # si existe
from models.cosecha_estanque import CosechaEstanque  # si existe

from enums.enums import EstanqueStatusEnum
from enums.roles import  Role
from utils.permissions import user_has_any_role, is_user_associated_to_granja


# ---------------------------
# Selectores y visibilidad
# ---------------------------

def _ensure_granja_visible(db: Session, user: Usuario, granja_id: int) -> None:
    if not user_has_any_role(user, [Role.admin_global]):
        if not is_user_associated_to_granja(db, user.usuario_id, granja_id):
            raise HTTPException(status_code=404, detail="granja_not_found: No existe o no tienes acceso.")

def _query_visible_estanques(db: Session, user: Usuario, granja_id: int):
    _ensure_granja_visible(db, user, granja_id)
    return db.query(Estanque).filter(Estanque.granja_id == granja_id)

def list_estanques(
    db: Session,
    user: Usuario,
    granja_id: int,
    q: Optional[str],
    status_filter: Optional[EstanqueStatusEnum],
    page: int,
    page_size: int,
    order_by: str,
    order: str,
) -> Tuple[List[Estanque], int]:
    query = _query_visible_estanques(db, user, granja_id)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (Estanque.nombre.ilike(like))
        )

    if status_filter:
        query = query.filter(Estanque.status == status_filter)

    valid_order = {"nombre": Estanque.nombre, "superficie_m2": Estanque.superficie_m2, "created_at": Estanque.created_at}
    col = valid_order.get(order_by, Estanque.created_at)
    query = query.order_by(col.asc() if order == "asc" else col.desc())

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total

def get_estanque_visible(db: Session, user: Usuario, granja_id: int, estanque_id: int) -> Estanque:
    _ensure_granja_visible(db, user, granja_id)
    obj = (
        db.query(Estanque)
          .filter(Estanque.granja_id == granja_id, Estanque.estanque_id == estanque_id)
          .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="estanque_not_found: No existe o no tienes acceso.")
    return obj


# ---------------------------
# Reglas de dominio (guards)
# ---------------------------

def _nombre_disponible(db: Session, granja_id: int, nombre: str, exclude_id: Optional[int] = None) -> bool:
    q = db.query(Estanque).filter(
        Estanque.granja_id == granja_id,
        func.lower(Estanque.nombre) == nombre.strip().lower()
    )
    if exclude_id is not None:
        q = q.filter(Estanque.estanque_id != exclude_id)
    return db.query(q.exists()).scalar() is False

def _estanque_en_uso(db: Session, estanque_id: int) -> bool:
    in_siembra = db.query(SiembraEstanque).filter(SiembraEstanque.estanque_id == estanque_id).first() is not None
    in_bio = db.query(Biometria).filter(Biometria.estanque_id == estanque_id).first() is not None
    in_cosecha = db.query(CosechaEstanque).filter(CosechaEstanque.estanque_id == estanque_id).first() is not None
    return in_siembra or in_bio or in_cosecha


# ---------------------------
# Mutaciones
# ---------------------------

def create_estanque(db: Session, user: Usuario, granja_id: int, data: Dict) -> Estanque:
    _ensure_granja_visible(db, user, granja_id)

    if db.query(Granja).filter(Granja.granja_id == granja_id).first() is None:
        raise HTTPException(status_code=404, detail="granja_not_found: No existe o no tienes acceso.")

    nombre = data.get("nombre", "")
    if not _nombre_disponible(db, granja_id, nombre):
        raise HTTPException(status_code=409, detail="pond_name_duplicated: Ya existe un estanque con ese nombre en esta granja.")

    # 🔧 FIX: siempre setear granja_id desde el path
    obj = Estanque(**data, granja_id=granja_id)

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_estanque(db: Session, user: Usuario, granja_id: int, estanque_id: int, changes: Dict) -> Estanque:
    obj = get_estanque_visible(db, user, granja_id, estanque_id)

    # Nombre único por granja
    new_nombre = changes.get("nombre")
    if new_nombre and new_nombre.strip().lower() != obj.nombre.strip().lower():
        if not _nombre_disponible(db, granja_id, new_nombre, exclude_id=estanque_id):
            raise HTTPException(status_code=409, detail="pond_name_duplicated: Ya existe un estanque con ese nombre en esta granja.")

    # Prohibir cerrar 'c' si está en uso
    if "status" in changes and changes["status"] == EstanqueStatusEnum.c:
        if _estanque_en_uso(db, estanque_id):
            raise HTTPException(status_code=409, detail="pond_in_use: No puedes cerrar un estanque con referencias operativas activas.")

    # Prohibir cambiar superficie si está en uso (para preservar históricos/calibraciones)
    if "superficie_m2" in changes and changes["superficie_m2"] is not None:
        if _estanque_en_uso(db, estanque_id):
            raise HTTPException(status_code=409, detail="pond_in_use_surface_change: No puedes modificar la superficie de un estanque en uso.")

    for k, v in changes.items():
        setattr(obj, k, v)

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def delete_estanque(db: Session, user: Usuario, granja_id: int, estanque_id: int) -> None:
    obj = get_estanque_visible(db, user, granja_id, estanque_id)

    if _estanque_en_uso(db, estanque_id):
        raise HTTPException(status_code=409, detail="pond_in_use: El estanque está referenciado por operaciones; no puede eliminarse.")

    db.delete(obj)
    db.commit()
