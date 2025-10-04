from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class CicloResumenBase(BaseModel):
    sob_final_real_pct: float = Field(..., ge=0, le=100)
    toneladas_cosechadas: float = Field(..., ge=0)
    n_estanques_cosechados: int = Field(..., ge=0)
    fecha_inicio_real: Optional[date]
    fecha_fin_real: Optional[date]
    notas_cierre: Optional[str] = Field(None, max_length=255)


class CicloResumenCreate(CicloResumenBase):
    ciclo_id: int


class CicloResumenOut(CicloResumenBase):
    ciclo_id: int
    created_at: datetime

    class Config:
        orm_mode = True
