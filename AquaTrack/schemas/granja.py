from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class GranjaBase(BaseModel):
    nombre: str = Field(..., max_length=150)
    ubicacion: Optional[str] = Field(None, max_length=200)
    descripcion: Optional[str]
    superficie_total_m2: float = Field(..., ge=0)


class GranjaCreate(GranjaBase):
    pass


class GranjaUpdate(BaseModel):
    nombre: Optional[str]
    ubicacion: Optional[str]
    descripcion: Optional[str]
    superficie_total_m2: Optional[float] = Field(None, ge=0)


class GranjaOut(GranjaBase):
    granja_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
