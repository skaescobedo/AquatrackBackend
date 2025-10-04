from datetime import datetime, date
from pydantic import BaseModel
from typing import Optional


class CosechaFechaLogBase(BaseModel):
    cosecha_estanque_id: int
    fecha_anterior: date
    fecha_nueva: date
    motivo: Optional[str]


class CosechaFechaLogCreate(CosechaFechaLogBase):
    changed_by: int


class CosechaFechaLogOut(CosechaFechaLogBase):
    cosecha_fecha_log_id: int
    changed_by: int
    changed_at: datetime

    class Config:
        orm_mode = True
