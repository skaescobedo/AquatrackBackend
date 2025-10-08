from pydantic import BaseModel, Field
from typing import List, Optional

class AuthLogin(BaseModel):
    username: str = Field(..., max_length=80)
    password: str = Field(..., min_length=1)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class FarmRole(BaseModel):
    granja_id: int
    rol_id: int
    estado: str

class MeOut(BaseModel):
    usuario_id: int
    username: str
    nombre: str
    apellido1: str
    apellido2: Optional[str] = None
    email: str
    is_admin_global: bool
    granjas: List[FarmRole] = []
