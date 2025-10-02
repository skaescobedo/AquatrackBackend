# utils/security.py
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Tuple

from passlib.context import CryptContext

# -----------------------------------------------------------------------------
# Configuración del hasher de contraseñas
# - bcrypt es un estándar seguro y ampliamente soportado.
# - Si más adelante quieres Argon2, puedes añadir un esquema adicional.
# -----------------------------------------------------------------------------
_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    # Coste por defecto de bcrypt (~12). Puedes subirlo si tu servidor lo aguanta.
    bcrypt__rounds=12,
)


# -----------------------------------------------------------------------------
# Contraseñas
# -----------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """
    Devuelve el hash de la contraseña usando bcrypt.
    - Nunca guardes 'password' en texto claro.
    - Al crear/actualizar Usuario, persiste este hash en 'password_hash'.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password inválido.")
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifica una contraseña en texto claro contra su hash almacenado.
    """
    if not password_hash:
        return False
    try:
        return _pwd_context.verify(password, password_hash)
    except Exception:
        # Si el hash está corrupto o con esquema desconocido, falla seguro.
        return False


# (Opcional) política simple de passwords; ajusta a tu gusto.
def is_password_strong(password: str) -> bool:
    """
    Regla mínima: longitud >= 8 y debe contener al menos 1 letra y 1 dígito.
    Amplía esta función si necesitas símbolos, mayúsculas, etc.
    """
    if not isinstance(password, str) or len(password) < 8:
        return False
    has_alpha = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    return has_alpha and has_digit


# -----------------------------------------------------------------------------
# Tokens de reseteo de contraseña
# - La tabla PasswordResetToken guarda token_hash (no el token en claro).
# - Generamos un token aleatorio (base64url), devolvemos:
#     (token_en_claro, token_hash_hex, expira_at)
# -----------------------------------------------------------------------------
def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def generate_password_reset_token(
    *, expires_in_minutes: int = 60
) -> Tuple[str, str, datetime]:
    """
    Genera un token seguro para reset de contraseña.

    Returns:
        token_plain (str): token en claro (base64url, sin '=')
        token_hash (str): SHA-256 hex del token (para guardar en DB)
        expira_at   (dt): instante de expiración en UTC
    """
    raw = secrets.token_bytes(32)  # 256 bits aleatorios
    token_plain = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    token_hash = _sha256_hex(token_plain.encode("utf-8"))

    expira_at = datetime.now(tz=timezone.utc) + timedelta(minutes=expires_in_minutes)
    return token_plain, token_hash, expira_at


def hash_reset_token(token_plain: str) -> str:
    """
    Convierte un token en claro a su SHA-256 hex (para compararlo con DB).
    """
    if not isinstance(token_plain, str) or not token_plain:
        raise ValueError("Token inválido.")
    return _sha256_hex(token_plain.encode("utf-8"))


def verify_reset_token(token_plain: str, token_hash_from_db: str) -> bool:
    """
    Compara en tiempo constante el SHA-256 del token en claro con el hash en DB.
    """
    if not token_plain or not token_hash_from_db:
        return False
    computed = hash_reset_token(token_plain)
    # hmac.compare_digest evita ataques de timing.
    return hmac.compare_digest(computed, token_hash_from_db)


def is_token_expired(expira_at: datetime) -> bool:
    """
    Devuelve True si expira_at ya pasó (comparación en UTC).
    """
    if expira_at.tzinfo is None:
        # Normaliza a UTC si te llega naive (por si tu ORM no usa tz)
        expira_at = expira_at.replace(tzinfo=timezone.utc)
    return datetime.now(tz=timezone.utc) >= expira_at


# -----------------------------------------------------------------------------
# Ejemplos de uso (comentados)
# -----------------------------------------------------------------------------
# # Crear usuario
# if not is_password_strong(req.password):
#     raise HTTPException(400, "Password débil.")
# user.password_hash = hash_password(req.password)
#
# # Login
# if not verify_password(req.password, user.password_hash):
#     raise HTTPException(401, "Credenciales inválidas.")
#
# # Crear token de reseteo
# token_plain, token_hash, expira_at = generate_password_reset_token(expires_in_minutes=30)
# db_obj = PasswordResetToken(usuario_id=user.id, token_hash=token_hash, expira_at=expira_at)
# # -> Envías 'token_plain' por email; NUNCA guardes ni muestres token_plain en DB.
#
# # Verificar token de reseteo
# if is_token_expired(db_obj.expira_at) or not verify_reset_token(token_recibido, db_obj.token_hash):
#     raise HTTPException(400, "Token inválido o expirado.")
