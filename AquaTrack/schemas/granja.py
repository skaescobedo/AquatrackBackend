from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal

class GranjaOut(BaseModel):
    granja_id: int
    nombre: str
    ubicacion: Optional[str]
    descripcion: Optional[str]
    superficie_total_m2: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GranjaCreate(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=150)
    ubicacion: Optional[str] = None
    descripcion: Optional[str] = None
    superficie_total_m2: Decimal

class GranjaUpdate(BaseModel):
    nombre: Optional[str] = None
    ubicacion: Optional[str] = None
    descripcion: Optional[str] = None
    superficie_total_m2: Optional[Decimal] = None
