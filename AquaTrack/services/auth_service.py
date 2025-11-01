# services/auth_service.py
"""
Servicio de autenticación.
Solo maneja login y generación de tokens JWT.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from utils.security import verify_password, create_access_token
from utils.datetime_utils import now_mazatlan
from models.user import Usuario


def authenticate_user(db: Session, username: str, password: str) -> Usuario:
    """
    Autenticar usuario con username y password.

    Args:
        db: Sesión de BD
        username: Username del usuario
        password: Contraseña en texto plano

    Returns:
        Usuario autenticado

    Raises:
        HTTPException: Si credenciales inválidas o usuario inactivo
    """
    user = db.query(Usuario).filter(Usuario.username == username).first()

    if not user or user.status != "a" or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas"
        )

    # Actualizar último login
    user.last_login_at = now_mazatlan()
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def issue_access_token(user: Usuario) -> str:
    """
    Generar token JWT para un usuario.

    Args:
        user: Usuario autenticado

    Returns:
        Token JWT como string
    """
    return create_access_token(subject=user.usuario_id)