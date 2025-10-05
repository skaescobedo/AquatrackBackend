# api/auth.py
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError

from utils.db import get_db
from utils.security import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_and_validate_token,
)
from utils.dependencies import get_current_user
from models.usuario import Usuario
from schemas.auth import (
    TokenPair,
    RefreshRequest,
    AccessTokenResponse,
    MeResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Helpers para tiempos (opcional): expone segundos al front
ACCESS_EXPIRE_MIN = 60  # si usas settings, puedes importarlo desde utils.security
REFRESH_EXPIRE_MIN = 60 * 24 * 7

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

@router.post("/login", response_model=TokenPair)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Swagger/Authorize mandará username y password como form-data.
    Devuelve un par de tokens (access/refresh).
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.usuario_id)  # <--- antes: user.id
    refresh_token = create_refresh_token(user.usuario_id)

    issued_at = _now_utc()
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        access_expires_in=ACCESS_EXPIRE_MIN * 60,
        refresh_expires_in=REFRESH_EXPIRE_MIN * 60,
        issued_at=issued_at,
    )

@router.post("/refresh", response_model=AccessTokenResponse)
def refresh_token(
    body: RefreshRequest,
    db: Session = Depends(get_db),
):
    """
    Recibe un refresh_token válido y emite un nuevo access_token.
    """
    try:
        payload = decode_and_validate_token(body.refresh_token, expected_type="refresh")
        user_id = int(payload.get("sub", "0"))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(Usuario, user_id)
    if not user or getattr(user, "estado", "a") != "a":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o inexistente",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user_id)
    issued_at = _now_utc()
    return AccessTokenResponse(
        access_token=access_token,
        token_type="bearer",
        access_expires_in=ACCESS_EXPIRE_MIN * 60,
        issued_at=issued_at,
    )

@router.get("/me", response_model=MeResponse)
def me(current_user: Usuario = Depends(get_current_user)):
    """
    Devuelve el usuario autenticado a partir del access token.
    """
    return current_user
