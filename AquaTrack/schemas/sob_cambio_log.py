from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class SobCambioLogBase(BaseModel):
    estanque_id: int
    ciclo_id: int
    sob_anterior_pct: float = Field(..., ge=0, le=100)
    sob_nueva_pct: float = Field(..., ge=0, le=100)
    fuente: str = Field(..., pattern="^(operativa_actual|ajuste_manual|reforecast)$")
    motivo: Optional[str]


class SobCambioLogCreate(SobCambioLogBase):
    changed_by: int


class SobCambioLogOut(SobCambioLogBase):
    sob_cambio_log_id: int
    changed_by: int
    changed_at: datetime

    class Config:
        orm_mode = True
