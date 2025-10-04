from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field
from schemas.common import Timestamps


class BiometriaBase(BaseModel):
    ciclo_id: int
    estanque_id: int
    fecha: date
    n_muestra: int = Field(..., gt=0)
    peso_muestra_g: float = Field(..., ge=0)
    pp_g: float = Field(..., ge=0)
    sob_usada_pct: float = Field(..., ge=0, le=100)
    incremento_g_sem: Optional[float] = Field(None, ge=0)
    notas: Optional[str] = Field(None, max_length=255)
    actualiza_sob_operativa: bool = False
    sob_fuente: Optional[str] = None


class BiometriaCreate(BiometriaBase):
    created_by: Optional[int] = None


class BiometriaOut(BiometriaBase, Timestamps):
    biometria_id: int
    created_by: Optional[int]

    class Config:
        orm_mode = True
