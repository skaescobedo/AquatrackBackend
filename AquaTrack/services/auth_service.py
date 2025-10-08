from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from utils.security import verify_password, create_access_token
from models.usuario import Usuario
from models.usuario_granja import UsuarioGranja

def login(db: Session, username: str, password: str) -> str:
    user = db.query(Usuario).filter(Usuario.username == username).first()
    if not user or user.estado != "a" or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    token = create_access_token(sub=user.username)
    return token

def get_profile(db: Session, user: Usuario):
    vinculaciones = (
        db.query(UsuarioGranja)
        .filter(UsuarioGranja.usuario_id == user.usuario_id)
        .all()
    )
    granjas = [
        {"granja_id": v.granja_id, "rol_id": v.rol_id, "estado": v.estado}
        for v in vinculaciones
    ]
    return {
        "usuario_id": user.usuario_id,
        "username": user.username,
        "nombre": user.nombre,
        "apellido1": user.apellido1,
        "apellido2": user.apellido2,
        "email": user.email,
        "is_admin_global": bool(user.is_admin_global),
        "granjas": granjas,
    }
