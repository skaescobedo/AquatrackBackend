from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from decimal import Decimal

class CicloResumenOut(BaseModel):
    ciclo_id: int
    sob_final_real_pct: Decimal
    toneladas_cosechadas: Decimal
    n_estanques_cosechados: int
    fecha_inicio_real: Optional[date]
    fecha_fin_real: Optional[date]
    notas_cierre: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class CicloResumenCreate(BaseModel):
    ciclo_id: int
    sob_final_real_pct: Decimal
    toneladas_cosechadas: Decimal
    n_estanques_cosechados: int
    fecha_inicio_real: Optional[date] = None
    fecha_fin_real: Optional[date] = None
    notas_cierre: Optional[str] = None

class CicloResumenUpdate(BaseModel):
    sob_final_real_pct: Optional[Decimal] = None
    toneladas_cosechadas: Optional[Decimal] = None
    n_estanques_cosechados: Optional[int] = None
    fecha_inicio_real: Optional[date] = None
    fecha_fin_real: Optional[date] = None
    notas_cierre: Optional[str] = None
