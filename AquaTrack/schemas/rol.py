from typing import Optional
from pydantic import BaseModel, Field


class RolBase(BaseModel):
    nombre: str = Field(..., max_length=80)
    descripcion: Optional[str] = Field(None, max_length=255)


class RolCreate(RolBase):
    pass


class RolUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=80)
    descripcion: Optional[str] = Field(None, max_length=255)


class RolOut(RolBase):
    rol_id: int

    model_config = {"from_attributes": True}
