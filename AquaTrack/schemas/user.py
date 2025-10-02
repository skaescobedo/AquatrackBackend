# schemas/user.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import EmailStr, Field, constr

from .shared import ORMModel, EstadoChar


# ============================================================
# Rol
# ============================================================

class RoleBase(ORMModel):
    nombre: constr(strip_whitespace=True, min_length=1, max_length=80) = Field(..., description="Nombre del rol (único).")
    descripcion: Optional[constr(strip_whitespace=True, max_length=255)] = None

class RoleCreate(RoleBase):
    pass

class RoleUpdate(ORMModel):
    nombre: Optional[constr(strip_whitespace=True, min_length=1, max_length=80)] = None
    descripcion: Optional[constr(strip_whitespace=True, max_length=255)] = None

class RoleRead(RoleBase):
    rol_id: int


# Mini para anidar en lecturas de usuario
class RoleMini(ORMModel):
    rol_id: int
    nombre: str


# ============================================================
# Usuario
# ============================================================

class UsuarioBase(ORMModel):
    nombre: constr(strip_whitespace=True, min_length=1, max_length=120)
    email: EmailStr
    # 'a' (activo) / 'i' (inactivo). No forzamos valores aquí; lo puedes validar en servicios.
    estado: EstadoChar = Field("a", description="Estado de un carácter, p. ej. 'a' activo, 'i' inactivo.")

class UsuarioCreate(UsuarioBase):
    # El servicio debe hashear este password antes de persistirlo en password_hash.
    password: constr(min_length=8, max_length=128) = Field(..., description="Password en texto claro (se hashea en el servicio).")
    # Asignación inicial opcional de roles
    rol_ids: Optional[List[int]] = Field(None, description="Lista de IDs de roles a asignar (opcional).")

class UsuarioUpdate(ORMModel):
    nombre: Optional[constr(strip_whitespace=True, min_length=1, max_length=120)] = None
    email: Optional[EmailStr] = None
    estado: Optional[EstadoChar] = None
    # Permite actualizar el password (el servicio lo hashea y lo guarda en password_hash)
    new_password: Optional[constr(min_length=8, max_length=128)] = Field(
        None, description="Nuevo password en texto claro; se hashea en actualización."
    )
    # Reemplazo del conjunto completo de roles
    rol_ids: Optional[List[int]] = Field(None, description="IDs de roles para reemplazar la asignación actual.")

class UsuarioRead(UsuarioBase):
    usuario_id: int
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    roles: List[RoleMini] = Field(default_factory=list)


# Mini útil para anidar en otros dominios
class UsuarioMini(ORMModel):
    usuario_id: int
    nombre: str
    email: EmailStr


# ============================================================
# UsuarioGranja (membresía usuario ↔ granja)
# ============================================================

class UsuarioGranjaBase(ORMModel):
    usuario_id: int
    granja_id: int
    estado: EstadoChar = Field("a")

class UsuarioGranjaCreate(UsuarioGranjaBase):
    pass

class UsuarioGranjaUpdate(ORMModel):
    estado: Optional[EstadoChar] = None

class UsuarioGranjaRead(UsuarioGranjaBase):
    usuario_granja_id: int
    created_at: datetime
    updated_at: datetime
    # Nota: si luego quieres anidar UsuarioMini o GranjaMini,
    # puedes agregarlos aquí como opcionales para respuestas enriquecidas.


# ============================================================
# Password Reset Token
# (la BD guarda token_hash; aquí recibimos token en claro para que el servicio lo hashee)
# ============================================================

class PasswordResetTokenBase(ORMModel):
    usuario_id: int
    expira_at: datetime

class PasswordResetTokenCreate(PasswordResetTokenBase):
    token: constr(strip_whitespace=True, min_length=16, max_length=255) = Field(
        ..., description="Token en texto claro; el servicio debe hashearlo y persistir token_hash."
    )

class PasswordResetTokenUpdate(ORMModel):
    # Si necesitas marcarlo como usado desde la API, puedes permitir setear used_at explícitamente,
    # o exponer un flag de 'used' para que el servicio lo traduzca a timestamp.
    used_at: Optional[datetime] = None

class PasswordResetTokenRead(PasswordResetTokenBase):
    token_id: int
    used_at: Optional[datetime] = None
    created_at: datetime
    # Deliberadamente NO exponemos token_hash ni el token en claro.
