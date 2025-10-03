from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from decimal import Decimal

class BiometriaOut(BaseModel):
    biometria_id: int
    ciclo_id: int
    estanque_id: int
    fecha: date
    n_muestra: int
    peso_muestra_g: Decimal
    pp_g: Decimal
    sob_usada_pct: Decimal
    incremento_g_sem: Optional[Decimal]
    notas: Optional[str]
    actualiza_sob_operativa: bool
    sob_fuente: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BiometriaCreate(BaseModel):
    ciclo_id: int
    estanque_id: int
    fecha: date
    n_muestra: int
    peso_muestra_g: Decimal
    pp_g: Decimal
    sob_usada_pct: Decimal
    incremento_g_sem: Optional[Decimal] = None
    notas: Optional[str] = None
    actualiza_sob_operativa: bool = False
    sob_fuente: Optional[str] = None
    created_by: Optional[int] = None

class BiometriaUpdate(BaseModel):
    fecha: Optional[date] = None
    n_muestra: Optional[int] = None
    peso_muestra_g: Optional[Decimal] = None
    pp_g: Optional[Decimal] = None
    sob_usada_pct: Optional[Decimal] = None
    incremento_g_sem: Optional[Decimal] = None
    notas: Optional[str] = None
    actualiza_sob_operativa: Optional[bool] = None
    sob_fuente: Optional[str] = None
