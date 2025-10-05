from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from schemas.common import Timestamps


class GranjaBase(BaseModel):
    nombre: str = Field(..., max_length=150)
    ubicacion: Optional[str] = Field(None, max_length=200)
    descripcion: Optional[str] = None
    superficie_total_m2: float = Field(..., ge=0)


class GranjaCreate(GranjaBase):
    pass


class GranjaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=150)
    ubicacion: Optional[str] = Field(None, max_length=200)
    descripcion: Optional[str] = None
    superficie_total_m2: Optional[float] = Field(None, ge=0)


class GranjaOut(GranjaBase, Timestamps):
    granja_id: int

    model_config = {"from_attributes": True}
