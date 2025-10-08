# schemas/proyeccion_linea.py
from __future__ import annotations
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from schemas.common import Timestamps

class ProyeccionLineaBase(BaseModel):
    edad_dias: int = Field(..., ge=0)
    semana_idx: int = Field(..., ge=0)
    fecha_plan: date
    pp_g: float = Field(..., ge=0)
    sob_pct_linea: float = Field(..., ge=0, le=100)
    incremento_g_sem: Optional[float] = Field(None)
    cosecha_flag: bool = False
    retiro_org_m2: Optional[float] = Field(None, ge=0)
    nota: Optional[str] = Field(None, max_length=255)

class ProyeccionLineaOut(ProyeccionLineaBase):
    proyeccion_linea_id: int
    proyeccion_id: int
    # Opcionales para ser tolerantes si luego los agregas en BD
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


    model_config = {"from_attributes": True}

class ProyeccionLineaCreate(ProyeccionLineaBase):
    pass

class ProyeccionLineasReplaceIn(BaseModel):
    items: List[ProyeccionLineaCreate]
