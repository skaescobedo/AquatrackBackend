from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class UserBase(BaseModel):
    username: str
    nombre: str
    apellido1: str
    apellido2: str | None = None
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(min_length=6)


class UserOut(UserBase):
    usuario_id: int
    is_admin_global: bool
    status: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    username: str
    password: str


# ============ SCHEMAS EXISTENTES ============

class UserCreateAdmin(BaseModel):
    """Admin crea usuario con más opciones"""
    username: str
    nombre: str
    apellido1: str
    apellido2: str | None = None
    email: EmailStr
    password: str = Field(min_length=6)
    is_admin_global: bool = False
    # Opcional: asignar a granja al crear (solo si NO es admin_global)
    granja_id: int | None = None
    rol_id: int | None = None


class UserUpdate(BaseModel):
    """Actualizar datos básicos del usuario"""
    nombre: str | None = None
    apellido1: str | None = None
    apellido2: str | None = None
    email: EmailStr | None = None


class ChangePasswordIn(BaseModel):
    """Cambiar contraseña (requiere contraseña actual)"""
    current_password: str
    new_password: str = Field(min_length=6)


class AssignUserToFarmIn(BaseModel):
    """Asignar usuario a granja con rol"""
    granja_id: int
    rol_id: int
    additional_scopes: list[str] | None = None  # Solo Admin Global puede usar esto


class UpdateUserFarmRoleIn(BaseModel):
    """Cambiar rol de usuario en granja"""
    rol_id: int


class UserFarmOut(BaseModel):
    """Información de usuario-granja con rol y scopes"""
    usuario_granja_id: int
    granja_id: int
    granja_nombre: str
    rol_id: int
    rol_nombre: str
    status: str
    scopes: list[str]  # ← NUEVO: Lista de permisos
    created_at: datetime

    class Config:
        from_attributes = True


class UserWithFarms(UserOut):
    """Usuario con sus granjas asignadas"""
    granjas: list[UserFarmOut] = []

    class Config:
        from_attributes = True


# ============ NUEVOS SCHEMAS PARA GESTIÓN DE SCOPES ============

class UpdateUserFarmScopesIn(BaseModel):
    """
    Agregar/quitar scopes opcionales a un usuario en una granja.
    Solo Admin Global puede usar este endpoint.

    Ejemplo:
    {
      "add_scopes": ["gestion_usuarios"],
      "remove_scopes": []
    }
    """
    add_scopes: list[str] = []
    remove_scopes: list[str] = []


class UserFarmScopesOut(BaseModel):
    """Respuesta al actualizar scopes"""
    usuario_granja_id: int
    granja_id: int
    rol_nombre: str
    scopes: list[str]
    message: str

    class Config:
        from_attributes = True