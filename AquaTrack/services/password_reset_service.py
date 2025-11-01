# services/password_reset_service.py
"""
Servicio para gestión de tokens de recuperación de contraseña.
"""
import secrets
import hashlib
from datetime import timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models.password_reset import PasswordResetToken
from models.user import Usuario
from utils.datetime_utils import now_mazatlan
from utils.security import hash_password
from services.email_service import send_password_reset_email
from config.settings import settings


def _hash_token(token: str) -> str:
    """Hashear token con SHA-256"""
    return hashlib.sha256(token.encode()).hexdigest()


def _check_rate_limit(db: Session, usuario_id: int) -> None:
    """
    Verificar límite de intentos por hora.

    Raises:
        HTTPException: Si excede el límite
    """
    one_hour_ago = now_mazatlan() - timedelta(hours=1)

    recent_attempts = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.usuario_id == usuario_id,
            PasswordResetToken.created_at >= one_hour_ago
        )
        .count()
    )

    if recent_attempts >= settings.PASSWORD_RESET_MAX_ATTEMPTS_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos. Intenta de nuevo en una hora."
        )


def request_password_reset(db: Session, email: str) -> dict:
    """
    Solicitar recuperación de contraseña.

    Pasos:
    1. Buscar usuario por email
    2. Verificar rate limit
    3. Generar token único
    4. Guardar token hasheado en BD
    5. Enviar email con link de reset

    Args:
        db: Sesión de BD
        email: Email del usuario

    Returns:
        dict con mensaje de éxito

    Raises:
        HTTPException: Si usuario no existe, está inactivo o excede rate limit
    """
    # Buscar usuario
    user = db.query(Usuario).filter(Usuario.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user.status != "a":
        raise HTTPException(status_code=403, detail="Usuario inactivo")

    # Verificar rate limit
    _check_rate_limit(db, user.usuario_id)

    # Generar token único (32 bytes = 64 caracteres hex)
    token = secrets.token_hex(32)
    token_hash = _hash_token(token)

    # Calcular expiración
    expira_at = now_mazatlan() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

    # Guardar en BD
    reset_token = PasswordResetToken(
        usuario_id=user.usuario_id,
        token_hash=token_hash,
        expira_at=expira_at,
        created_at=now_mazatlan()
    )
    db.add(reset_token)
    db.commit()

    # Construir link de reset
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    # Enviar email
    email_sent = send_password_reset_email(
        to_email=user.email,
        reset_link=reset_link,
        user_name=user.nombre
    )

    if not email_sent:
        # Si falla el email, eliminar token
        db.delete(reset_token)
        db.commit()
        raise HTTPException(status_code=500, detail="Error al enviar email")

    return {
        "message": "Se ha enviado un correo con instrucciones para restablecer tu contraseña"
    }


def reset_password(db: Session, token: str, new_password: str) -> dict:
    """
    Resetear contraseña con token.

    Pasos:
    1. Hashear token recibido
    2. Buscar token en BD
    3. Validar que no esté expirado ni usado
    4. Cambiar contraseña del usuario
    5. Marcar token como usado

    Args:
        db: Sesión de BD
        token: Token en texto plano (del email)
        new_password: Nueva contraseña

    Returns:
        dict con mensaje de éxito

    Raises:
        HTTPException: Si token inválido, expirado o ya usado
    """
    # Hashear token
    token_hash = _hash_token(token)

    # Buscar token en BD
    reset_token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first()
    )

    if not reset_token:
        raise HTTPException(status_code=400, detail="Token inválido")

    # Validar que no esté expirado
    if reset_token.expira_at < now_mazatlan():
        raise HTTPException(status_code=400, detail="Token expirado")

    # Validar que no esté usado
    if reset_token.used_at is not None:
        raise HTTPException(status_code=400, detail="Token ya utilizado")

    # Obtener usuario
    user = db.get(Usuario, reset_token.usuario_id)
    if not user or user.status != "a":
        raise HTTPException(status_code=403, detail="Usuario no disponible")

    # Cambiar contraseña
    user.password_hash = hash_password(new_password)

    # Marcar token como usado
    reset_token.used_at = now_mazatlan()

    db.add(user)
    db.add(reset_token)
    db.commit()

    return {
        "message": "Contraseña restablecida exitosamente"
    }


def cleanup_expired_tokens(db: Session) -> int:
    """
    Limpiar tokens expirados de la BD (tarea de mantenimiento).

    Se recomienda ejecutar periódicamente (ej: cron job diario).

    Args:
        db: Sesión de BD

    Returns:
        Número de tokens eliminados
    """
    now = now_mazatlan()

    # Eliminar tokens expirados hace más de 7 días
    cutoff_date = now - timedelta(days=7)

    deleted = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.expira_at < cutoff_date)
        .delete(synchronize_session=False)
    )

    db.commit()

    return deleted