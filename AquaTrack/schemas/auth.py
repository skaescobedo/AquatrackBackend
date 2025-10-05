# schemas/auth.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

# ===== Entradas =====
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=80)
    password: str = Field(..., min_length=8)

class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20)

class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)

class RequestPasswordReset(BaseModel):
    email: EmailStr

class ConfirmPasswordReset(BaseModel):
    token: str = Field(..., min_length=20)
    new_password: str = Field(..., min_length=8)

# Opcional: Registro (si no quieres usar UsuarioCreate directamente)
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    nombre: str = Field(..., max_length=30)
    apellido1: str = Field(..., max_length=30)
    apellido2: Optional[str] = Field(None, max_length=30)
    email: EmailStr
    password: str = Field(..., min_length=8)

# ===== Internos (no exponer completos) =====
class TokenPayload(BaseModel):
    # Carga útil del JWT (access/refresh)
    sub: str                        # usualmente user_id como string
    scopes: Optional[List[str]] = None
    iat: Optional[int] = None       # issued at (epoch)
    exp: Optional[int] = None       # expiration (epoch)
    jti: Optional[str] = None       # id único del token
    type: Optional[str] = None      # "access" | "refresh"  <-- unificado a 'type'

# ===== Salidas =====
class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # campos informativos opcionales (útiles para front)
    access_expires_in: Optional[int] = None   # segundos
    refresh_expires_in: Optional[int] = None  # segundos
    issued_at: Optional[datetime] = None

class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    access_expires_in: Optional[int] = None
    issued_at: Optional[datetime] = None

class MessageOut(BaseModel):
    message: str

class MeResponse(BaseModel):
    usuario_id: int
    username: str
    email: EmailStr
    nombre: str
    apellido1: str
    apellido2: str | None = None
    estado: str
    model_config = {"from_attributes": True}

# ---- Compatibilidad suave (si en alguna parte importaste estos) ----
class Token(BaseModel):  # DEPRECATED: usar TokenPair
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshInput(BaseModel):  # DEPRECATED: usar RefreshRequest
    refresh_token: str

__all__ = [
    # Entradas
    "LoginRequest", "RefreshRequest", "ChangePasswordRequest",
    "RequestPasswordReset", "ConfirmPasswordReset", "RegisterRequest",
    # Internos
    "TokenPayload",
    # Salidas
    "TokenPair", "AccessTokenResponse", "MessageOut", "MeResponse",
    # Compatibilidad
    "Token", "RefreshInput",
]
