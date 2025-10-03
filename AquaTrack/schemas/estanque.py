from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal

class EstanqueOut(BaseModel):
    estanque_id: int
    granja_id: int
    nombre: str
    superficie_m2: Decimal
    status: str
    sob_estanque_pct: Decimal
    sob_updated_at: Optional[datetime]
    sob_updated_by: Optional[int]
    sob_source: Optional[str]
    sob_note: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class EstanqueCreate(BaseModel):
    granja_id: int
    nombre: str = Field(..., min_length=2, max_length=120)
    superficie_m2: Decimal
    status: str = "i"
    sob_estanque_pct: Decimal = 100.0

class EstanqueUpdate(BaseModel):
    nombre: Optional[str] = None
    superficie_m2: Optional[Decimal] = None
    status: Optional[str] = None
    sob_estanque_pct: Optional[Decimal] = None
    sob_updated_by: Optional[int] = None
    sob_source: Optional[str] = None
    sob_note: Optional[str] = None
