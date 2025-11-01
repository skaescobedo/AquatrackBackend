from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status

from models.user import Usuario
from models.user import UsuarioGranja
from models.farm import Granja
from models.role import Rol
from schemas.user import (
    UserCreateAdmin,
    UserUpdate,
    ChangePasswordIn,
    AssignUserToFarmIn,
    UpdateUserFarmRoleIn,
    UserFarmOut,
)
from utils.security import hash_password, verify_password


def list_users(
    db: Session,
    granja_id: int | None = None,
    status_filter: str | None = None,
    search: str | None = None,
) -> list[Usuario]:
    """Listar usuarios con filtros opcionales"""
    q = db.query(Usuario)

    # Filtro por granja
    if granja_id is not None:
        q = q.join(UsuarioGranja).filter(UsuarioGranja.granja_id == granja_id)

    # Filtro por status
    if status_filter:
        q = q.filter(Usuario.status == status_filter)

    # Búsqueda por nombre, apellido, username o email
    if search:
        search_pattern = f"%{search}%"
        q = q.filter(
            or_(
                Usuario.nombre.ilike(search_pattern),
                Usuario.apellido1.ilike(search_pattern),
                Usuario.apellido2.ilike(search_pattern),
                Usuario.username.ilike(search_pattern),
                Usuario.email.ilike(search_pattern),
            )
        )

    return q.order_by(Usuario.nombre.asc()).all()


def get_user(db: Session, usuario_id: int) -> Usuario:
    """Obtener usuario por ID"""
    user = db.get(Usuario, usuario_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )
    return user


def create_user(db: Session, payload: UserCreateAdmin) -> Usuario:
    """Crear usuario (con o sin asignación a granja)"""
    try:
        # Validar username único
        existing = db.query(Usuario).filter(Usuario.username == payload.username).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El username ya existe",
            )

        # Validar email único
        existing_email = db.query(Usuario).filter(Usuario.email == payload.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El email ya existe",
            )

        # Si NO es admin_global y se proporciona granja, validar que existan
        if not payload.is_admin_global and payload.granja_id and payload.rol_id:
            granja = db.get(Granja, payload.granja_id)
            if not granja:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Granja no encontrada",
                )
            rol = db.get(Rol, payload.rol_id)
            if not rol:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Rol no encontrado",
                )

        # Crear usuario
        user = Usuario(
            username=payload.username,
            nombre=payload.nombre,
            apellido1=payload.apellido1,
            apellido2=payload.apellido2,
            email=payload.email,
            password_hash=hash_password(payload.password),
            is_admin_global=payload.is_admin_global,
            status="a",
        )
        db.add(user)
        db.flush()

        # Si NO es admin_global y se proporciona granja_id, asignar
        if not payload.is_admin_global and payload.granja_id and payload.rol_id:
            user_farm = UsuarioGranja(
                usuario_id=user.usuario_id,
                granja_id=payload.granja_id,
                rol_id=payload.rol_id,
                status="a",
            )
            db.add(user_farm)

        db.commit()
        db.refresh(user)
        return user
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def update_user(db: Session, usuario_id: int, payload: UserUpdate) -> Usuario:
    """Actualizar datos básicos del usuario"""
    user = db.get(Usuario, usuario_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )

    data = payload.model_dump(exclude_unset=True)

    # Validar email único si se está actualizando
    if "email" in data and data["email"] is not None:
        existing = (
            db.query(Usuario)
            .filter(Usuario.email == data["email"], Usuario.usuario_id != usuario_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El email ya está en uso",
            )

    for k, v in data.items():
        setattr(user, k, v)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def change_password(
    db: Session, usuario_id: int, payload: ChangePasswordIn
) -> Usuario:
    """Cambiar contraseña (requiere contraseña actual)"""
    user = db.get(Usuario, usuario_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )

    # Verificar contraseña actual
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña actual incorrecta",
        )

    # Actualizar contraseña
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def soft_delete_user(db: Session, usuario_id: int) -> Usuario:
    """Desactivar usuario (status='i')"""
    user = db.get(Usuario, usuario_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )

    if user.status == "i":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya está inactivo",
        )

    user.status = "i"
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def hard_delete_user(db: Session, usuario_id: int) -> dict:
    """Eliminar permanentemente (solo admin)"""
    user = db.get(Usuario, usuario_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )

    # Eliminar relaciones usuario_granja primero
    db.query(UsuarioGranja).filter(UsuarioGranja.usuario_id == usuario_id).delete()

    db.delete(user)
    db.commit()
    return {"detail": "Usuario eliminado permanentemente"}


def assign_user_to_farm(
    db: Session, usuario_id: int, payload: AssignUserToFarmIn
) -> UsuarioGranja:
    """Asignar usuario a granja con rol"""
    user = db.get(Usuario, usuario_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )

    # Admin global no necesita asignación
    if user.is_admin_global:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admin global tiene acceso a todas las granjas automáticamente",
        )

    granja = db.get(Granja, payload.granja_id)
    if not granja:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Granja no encontrada"
        )

    rol = db.get(Rol, payload.rol_id)
    if not rol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado"
        )

    # Validar que no exista ya la asignación
    existing = (
        db.query(UsuarioGranja)
        .filter(
            UsuarioGranja.usuario_id == usuario_id,
            UsuarioGranja.granja_id == payload.granja_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya está asignado a esta granja",
        )

    user_farm = UsuarioGranja(
        usuario_id=usuario_id,
        granja_id=payload.granja_id,
        rol_id=payload.rol_id,
        status="a",
    )
    db.add(user_farm)
    db.commit()
    db.refresh(user_farm)
    return user_farm


def remove_user_from_farm(db: Session, usuario_id: int, granja_id: int) -> dict:
    """Quitar usuario de granja (eliminar registro usuario_granja)"""
    user = db.get(Usuario, usuario_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )

    if user.is_admin_global:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admin global no puede ser removido de granjas",
        )

    user_farm = (
        db.query(UsuarioGranja)
        .filter(
            UsuarioGranja.usuario_id == usuario_id,
            UsuarioGranja.granja_id == granja_id,
        )
        .first()
    )

    if not user_farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no está asignado a esta granja",
        )

    db.delete(user_farm)
    db.commit()
    return {"detail": "Usuario removido de la granja"}


def update_user_farm_role(
    db: Session, usuario_id: int, granja_id: int, payload: UpdateUserFarmRoleIn
) -> UsuarioGranja:
    """Cambiar rol de usuario en granja"""
    user_farm = (
        db.query(UsuarioGranja)
        .filter(
            UsuarioGranja.usuario_id == usuario_id,
            UsuarioGranja.granja_id == granja_id,
        )
        .first()
    )

    if not user_farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no está asignado a esta granja",
        )

    rol = db.get(Rol, payload.rol_id)
    if not rol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado"
        )

    user_farm.rol_id = payload.rol_id
    db.add(user_farm)
    db.commit()
    db.refresh(user_farm)
    return user_farm


def get_user_farms(db: Session, usuario_id: int) -> list[UserFarmOut]:
    """Listar granjas del usuario con información de rol"""
    user = db.get(Usuario, usuario_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )

    # Si es admin global, retornar todas las granjas
    if user.is_admin_global:
        granjas = db.query(Granja).filter(Granja.is_active == True).all()
        return [
            UserFarmOut(
                usuario_granja_id=0,
                granja_id=g.granja_id,
                granja_nombre=g.nombre,
                rol_id=0,
                rol_nombre="Admin Global",
                status="a",
                created_at=user.created_at,
                scopes=[],
            )
            for g in granjas
        ]

    # Usuario normal: obtener sus granjas de usuario_granja
    user_farms = (
        db.query(UsuarioGranja, Granja, Rol)
        .join(Granja, UsuarioGranja.granja_id == Granja.granja_id)
        .join(Rol, UsuarioGranja.rol_id == Rol.rol_id)
        .filter(UsuarioGranja.usuario_id == usuario_id)
        .all()
    )

    return [
        UserFarmOut(
            usuario_granja_id=uf.usuario_granja_id,
            granja_id=uf.granja_id,
            granja_nombre=g.nombre,
            rol_id=uf.rol_id,
            rol_nombre=r.nombre,
            status=uf.status,
            created_at=uf.created_at,
            scopes=uf.scopes or [],
        )
        for uf, g, r in user_farms
    ]