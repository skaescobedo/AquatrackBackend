from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class ProyeccionLineaBase(BaseModel):
    proyeccion_id: int
    edad_dias: int = Field(..., ge=0)
    semana_idx: int = Field(..., ge=0)
    fecha_plan: date
    pp_g: float = Field(..., ge=0)
    incremento_g_sem: Optional[float] = Field(None, ge=0)
    sob_pct_linea: float = Field(..., ge=0, le=100)
    cosecha_flag: bool = False
    retiro_org_m2: Optional[float] = Field(None, ge=0)
    nota: Optional[str] = Field(None, max_length=255)


class ProyeccionLineaCreate(ProyeccionLineaBase):
    pass


class ProyeccionLineaOut(ProyeccionLineaBase):
    proyeccion_linea_id: int

    model_config = {"from_attributes": True}