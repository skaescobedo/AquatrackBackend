from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional


class BiometriaBase(BaseModel):
    ciclo_id: int
    estanque_id: int
    fecha: date
    n_muestra: int = Field(..., gt=0)
    peso_muestra_g: float = Field(..., ge=0)
    pp_g: float = Field(..., ge=0)
    sob_usada_pct: float = Field(..., ge=0, le=100)
    incremento_g_sem: Optional[float] = Field(None, ge=0)
    notas: Optional[str]
    actualiza_sob_operativa: bool = False
    sob_fuente: Optional[str] = Field(None, pattern="^(operativa_actual|ajuste_manual|reforecast)?$")


class BiometriaCreate(BiometriaBase):
    created_by: Optional[int]


class BiometriaOut(BiometriaBase):
    biometria_id: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
