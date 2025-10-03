from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from decimal import Decimal

class ProyeccionOut(BaseModel):
    proyeccion_id: int
    ciclo_id: int
    version: str
    descripcion: Optional[str]
    status: str
    is_current: bool
    published_at: Optional[datetime]
    creada_por: Optional[int]
    source_type: Optional[str]
    source_ref: Optional[str]
    parent_version_id: Optional[int]
    siembra_ventana_inicio: Optional[date]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ProyeccionCreate(BaseModel):
    ciclo_id: int
    version: str
    descripcion: Optional[str] = None
    status: str = "b"
    is_current: bool = False
    creada_por: Optional[int] = None

class ProyeccionUpdate(BaseModel):
    descripcion: Optional[str] = None
    status: Optional[str] = None
    is_current: Optional[bool] = None
    published_at: Optional[datetime] = None
    source_type: Optional[str] = None
    source_ref: Optional[str] = None


class ProyeccionLineaOut(BaseModel):
    proyeccion_linea_id: int
    proyeccion_id: int
    edad_dias: int
    semana_idx: int
    fecha_plan: date
    pp_g: Decimal
    incremento_g_sem: Optional[Decimal]
    sob_pct_linea: Decimal
    cosecha_flag: int
    retiro_org_m2: Optional[Decimal]
    nota: Optional[str]

    class Config:
        from_attributes = True

class ProyeccionLineaCreate(BaseModel):
    proyeccion_id: int
    edad_dias: int
    semana_idx: int
    fecha_plan: date
    pp_g: Decimal
    sob_pct_linea: Decimal
    cosecha_flag: int = 0
    incremento_g_sem: Optional[Decimal] = None
    retiro_org_m2: Optional[Decimal] = None
    nota: Optional[str] = None

class ProyeccionLineaUpdate(BaseModel):
    edad_dias: Optional[int] = None
    semana_idx: Optional[int] = None
    fecha_plan: Optional[date] = None
    pp_g: Optional[Decimal] = None
    sob_pct_linea: Optional[Decimal] = None
    cosecha_flag: Optional[int] = None
    incremento_g_sem: Optional[Decimal] = None
    retiro_org_m2: Optional[Decimal] = None
    nota: Optional[str] = None
