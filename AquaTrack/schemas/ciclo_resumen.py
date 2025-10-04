from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional


class CicloResumenBase(BaseModel):
    ciclo_id: int
    sob_final_real_pct: float = Field(..., ge=0, le=100)
    toneladas_cosechadas: float = Field(..., ge=0)
    n_estanques_cosechados: int = Field(..., ge=0)
    fecha_inicio_real: Optional[date]
    fecha_fin_real: Optional[date]
    notas_cierre: Optional[str]


class CicloResumenCreate(CicloResumenBase):
    pass


class CicloResumenOut(CicloResumenBase):
    created_at: datetime

    class Config:
        orm_mode = True
