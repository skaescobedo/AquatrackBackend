from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class SiembraFechaLogBase(BaseModel):
    siembra_estanque_id: int
    fecha_anterior: date
    fecha_nueva: date
    motivo: Optional[str] = Field(None, max_length=255)


class SiembraFechaLogCreate(SiembraFechaLogBase):
    changed_by: int


class SiembraFechaLogOut(SiembraFechaLogBase):
    siembra_fecha_log_id: int
    changed_by: int
    changed_at: datetime

    class Config:
        orm_mode = True
