# schemas/cosecha_fecha_log.py
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field

class CosechaFechaLogBase(BaseModel):
    cosecha_estanque_id: int
    fecha_anterior: date
    fecha_nueva: date
    motivo: Optional[str] = Field(None, max_length=255)

class CosechaFechaLogCreate(CosechaFechaLogBase):
    changed_by: int

class CosechaFechaLogOut(CosechaFechaLogBase):
    cosecha_fecha_log_id: int
    changed_by: int
    changed_at: datetime

    model_config = {"from_attributes": True}
