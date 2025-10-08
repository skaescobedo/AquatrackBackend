from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from models.usuario import Usuario
from models.usuario_granja import UsuarioGranja
from models.rol import Rol

# Mapa de scopes por rol (según tu plan)
SCOPES_BY_ROLE = {
    "admin_granja": {
        "farms:read", "farms:write", "ponds:read", "ponds:write",
        "cycles:read", "cycles:create", "cycles:close",
        "projections:read", "projections:publish", "projections:reforecast",
        "seeding:plan", "seeding:reprogram", "seeding:confirm",
        "harvest:plan", "harvest:reprogram", "harvest:confirm", "harvest:cancel",
        "biometry:write", "sob:update", "files:read", "tasks:write",
    },
    "biologo": {
        "farms:read", "ponds:read",
        "cycles:read",
        "projections:read", "projections:reforecast",
        "seeding:plan", "seeding:reprogram",
        "harvest:plan", "harvest:reprogram",
        "biometry:write", "files:read", "tasks:read",
    },
    "operador": {
        "farms:read", "ponds:read", "cycles:read", "projections:read",
        "biometry:write", "tasks:read", "files:read",
    },
    "consultor": {"farms:read", "ponds:read", "cycles:read", "projections:read", "files:read"},
}

def ensure_user_in_farm_or_admin(db: Session, user: Usuario, granja_id: int):
    if user.is_admin_global:
        return
    vinc = (
        db.query(UsuarioGranja)
        .filter(
            UsuarioGranja.usuario_id == user.usuario_id,
            UsuarioGranja.granja_id == granja_id,
            UsuarioGranja.estado == "a",
        )
        .first()
    )
    if not vinc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden: farm_access_required")

def _role_name_for_user_in_farm(db: Session, user: Usuario, granja_id: int) -> str | None:
    vinc = (
        db.query(UsuarioGranja)
        .filter(
            UsuarioGranja.usuario_id == user.usuario_id,
            UsuarioGranja.granja_id == granja_id,
            UsuarioGranja.estado == "a",
        )
        .first()
    )
    if not vinc:
        return None
    r = db.query(Rol).filter(Rol.rol_id == vinc.rol_id).first()
    return r.nombre if r else None

def require_scopes(db: Session, user: Usuario, granja_id: int, required: set[str]):
    if user.is_admin_global:
        return
    role_name = _role_name_for_user_in_farm(db, user, granja_id)
    if not role_name:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden: farm_access_required")
    scopes = SCOPES_BY_ROLE.get(role_name, set())
    if not required.issubset(scopes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden: insufficient_scope")
