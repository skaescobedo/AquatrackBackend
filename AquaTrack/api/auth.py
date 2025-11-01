# api/auth.py
"""
API de autenticación.
Endpoints: login, me, forgot-password, reset-password.
"""
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from schemas.user import Token, UserOut
from schemas.password_reset import ForgotPasswordIn, ResetPasswordIn, PasswordResetResponse
from services.auth_service import authenticate_user, issue_access_token
from services.password_reset_service import request_password_reset, reset_password
from models.user import Usuario

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/token",
    response_model=Token,
    summary="Login (OAuth2)",
    description=(
        "Autenticación usando OAuth2 Password Flow.\n\n"
        "**Formato:** `application/x-www-form-urlencoded` (estándar OAuth2)\n\n"
        "**Campos:**\n"
        "- `username`: Username del usuario\n"
        "- `password`: Contraseña\n\n"
        "**Response:**\n"
        "- `access_token`: Token JWT para usar en header `Authorization: Bearer <token>`\n"
        "- `token_type`: Siempre `bearer`"
    )
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login con username y password"""
    user = authenticate_user(db, form_data.username, form_data.password)
    token = issue_access_token(user)
    return {"access_token": token, "token_type": "bearer"}


@router.get(
    "/me",
    response_model=UserOut,
    summary="Obtener usuario actual",
    description=(
        "Retorna la información del usuario autenticado.\n\n"
        "**Requiere autenticación:** Sí (Bearer token en header)\n\n"
        "**Response:**\n"
        "- Datos completos del usuario actual"
    )
)
def me(current_user: Usuario = Depends(get_current_user)):
    """Obtener información del usuario autenticado"""
    return current_user


@router.post(
    "/forgot-password",
    response_model=PasswordResetResponse,
    summary="Solicitar recuperación de contraseña",
    description=(
        "Envía un email con un link para restablecer la contraseña.\n\n"
        "**Proceso:**\n"
        "1. Valida que el email exista\n"
        "2. Verifica rate limit (máx 5 intentos por hora)\n"
        "3. Genera token único con expiración de 30 minutos\n"
        "4. Envía email con link de reset\n\n"
        "**Nota:** Por seguridad, siempre retorna éxito incluso si el email no existe."
    )
)
def forgot_password(
    payload: ForgotPasswordIn,
    db: Session = Depends(get_db)
):
    """Solicitar recuperación de contraseña"""
    try:
        return request_password_reset(db, payload.email)
    except Exception:
        # Por seguridad, siempre retornar éxito (no revelar si email existe)
        return {
            "message": "Si el correo existe, recibirás instrucciones para restablecer tu contraseña"
        }


@router.post(
    "/reset-password",
    response_model=PasswordResetResponse,
    summary="Restablecer contraseña con token",
    description=(
        "Cambia la contraseña usando el token recibido por email.\n\n"
        "**Validaciones:**\n"
        "- Token debe ser válido (existe en BD)\n"
        "- Token no debe estar expirado (< 30 minutos)\n"
        "- Token no debe haber sido usado previamente\n"
        "- Nueva contraseña debe tener mínimo 6 caracteres\n\n"
        "**Efecto:**\n"
        "- Cambia la contraseña del usuario\n"
        "- Marca el token como usado (no reutilizable)"
    )
)
def reset_password_endpoint(
    payload: ResetPasswordIn,
    db: Session = Depends(get_db)
):
    """Restablecer contraseña con token"""
    return reset_password(db, payload.token, payload.new_password)