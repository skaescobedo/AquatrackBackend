from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from schemas.enums import SobFuenteEnum


class SobCambioLogBase(BaseModel):
    estanque_id: int
    ciclo_id: int
    sob_anterior_pct: float = Field(..., ge=0, le=100)
    sob_nueva_pct: float = Field(..., ge=0, le=100)
    fuente: SobFuenteEnum
    motivo: Optional[str] = Field(None, max_length=255)


class SobCambioLogCreate(SobCambioLogBase):
    changed_by: int


class SobCambioLogOut(SobCambioLogBase):
    sob_cambio_log_id: int
    changed_by: int
    changed_at: datetime

    class Config:
        orm_mode = True
