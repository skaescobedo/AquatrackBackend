from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date

class BiometriaCreate(BaseModel):
    estanque_id: int
    n_muestra: int = Field(gt=0)
    # peso total de la muestra (g) o promedio * n, según tu operación; aquí lo tomamos como peso total.
    peso_muestra_g: float = Field(ge=0)
    # SOB opcional: si no se envía, se usa la operativa vigente o la de proyección.
    sob_usada_pct: Optional[float] = Field(default=None, ge=0, le=100)
    notas: Optional[str] = None

class BiometriaOut(BaseModel):
    biometria_id: int
    ciclo_id: int
    estanque_id: int
    fecha: date               # fecha (día) de la biometría
    created_at: datetime      # timestamp exacto de carga
    n_muestra: int
    peso_muestra_g: float
    pp_g: float
    incremento_g_sem: Optional[float] = None
    sob_usada_pct: float
    sob_fuente: Optional[str] = None
    actualiza_sob_operativa: int
    notas: Optional[str] = None
