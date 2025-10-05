# utils/security.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import uuid4

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config.settings import settings
from enums.enums import UsuarioEstadoEnum
from models.usuario import Usuario

# ============================
# Config
# ============================
ALGORITHM = getattr(settings, "ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60))
REFRESH_TOKEN_EXPIRE_MINUTES = int(getattr(settings, "REFRESH_TOKEN_EXPIRE_MINUTES", 60*24*7))
SECRET_KEY = getattr(settings, "SECRET_KEY")
REFRESH_SECRET_KEY = getattr(settings, "REFRESH_SECRET_KEY", SECRET_KEY)

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============================
# Password hashing
# ============================
def get_password_hash(password: str) -> str:
    return _pwd_ctx.hash(password)

def verify_password(plain_password: str, password_hash: str) -> bool:
    return _pwd_ctx.verify(plain_password, password_hash)

# ============================
# JWT helpers
# ============================
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _encode(payload: Dict[str, Any], *, secret: str) -> str:
    return jwt.encode(payload, secret, algorithm=ALGORITHM)

def _decode(token: str, *, secret: str) -> Dict[str, Any]:
    return jwt.decode(token, secret, algorithms=[ALGORITHM])


# crea tokens con "sub" = usuario_id (string)
def create_access_token(subject: int | str, extra_claims: dict | None = None) -> str:
    user_id_str = str(subject)  # ya lo pasaremos con usuario_id
    now = _now_utc()
    payload = {
        "sub": user_id_str,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "jti": str(uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return _encode(payload, secret=SECRET_KEY)

def create_refresh_token(subject: int | str, extra_claims: dict | None = None) -> str:
    user_id_str = str(subject)
    now = _now_utc()
    payload = {
        "sub": user_id_str,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "jti": str(uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return _encode(payload, secret=REFRESH_SECRET_KEY)

def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodifica sin validar el 'type' (elige secret por heurística, primero access, luego refresh).
    Útil si solo quieres leer claims y tú decides cómo validarlos.
    """
    try:
        # Intento con access
        return _decode(token, secret=SECRET_KEY)
    except JWTError:
        # Intento con refresh
        return _decode(token, secret=REFRESH_SECRET_KEY)

def decode_and_validate_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    """
    Decodifica y valida:
      - que el token no esté expirado
      - que tenga 'sub' y 'type'
      - que el 'type' coincida con expected_type ('access' o 'refresh')
      - usa el secret correcto según expected_type
    """
    if expected_type not in {"access", "refresh"}:
        raise JWTError("expected_type inválido")

    secret = SECRET_KEY if expected_type == "access" else REFRESH_SECRET_KEY
    payload = _decode(token, secret=secret)

    tok_type = payload.get("type")
    sub = payload.get("sub")
    if not sub or not tok_type:
        raise JWTError("Token sin 'sub' o 'type'")

    if tok_type != expected_type:
        raise JWTError(f"Tipo de token inválido: se esperaba '{expected_type}' y llegó '{tok_type}'")

    return payload

# ============================
# Auth de usuario
# ============================
def authenticate_user(db: Session, username_or_email: str, password: str) -> Optional[Usuario]:
    # Ajustado a tus campos reales
    user = (
        db.query(Usuario)
        .filter((Usuario.username == username_or_email) | (Usuario.email == username_or_email))
        .first()
    )
    if not user:
        return None
    if user.estado != UsuarioEstadoEnum.a:  # si importas el Enum, o compara con "a"
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
