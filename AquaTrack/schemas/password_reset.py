# schemas/password_reset.py
from pydantic import BaseModel, EmailStr, Field


class ForgotPasswordIn(BaseModel):
    """Request para solicitar recuperación de contraseña"""
    email: EmailStr


class ResetPasswordIn(BaseModel):
    """Request para resetear contraseña con token"""
    token: str = Field(..., min_length=32, max_length=64)
    new_password: str = Field(..., min_length=6, max_length=100)


class PasswordResetResponse(BaseModel):
    """Response genérico para operaciones de password reset"""
    message: str