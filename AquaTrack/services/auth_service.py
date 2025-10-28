from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from utils.security import verify_password, hash_password, create_access_token
from models.user import Usuario
from schemas.user import UserCreate

def authenticate_user(db: Session, username: str, password: str) -> Usuario:
    user = db.query(Usuario).filter(Usuario.username == username).first()
    if not user or user.status != "a" or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    user.last_login_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def issue_access_token(user: Usuario) -> str:
    return create_access_token(subject=user.usuario_id)

def create_user(db: Session, data: UserCreate) -> Usuario:
    if db.query(Usuario).filter((Usuario.username == data.username) | (Usuario.email == data.email)).first():
        raise HTTPException(status_code=400, detail="Usuario o email ya existen")
    user = Usuario(
        username=data.username,
        nombre=data.nombre,
        apellido1=data.apellido1,
        apellido2=data.apellido2,
        email=data.email,
        password_hash=hash_password(data.password),
        status="a",
        is_admin_global=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
