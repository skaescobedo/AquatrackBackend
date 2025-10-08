from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import date, datetime

SyncPolicy = Literal["none", "sync", "regen"]

class ProyeccionOut(BaseModel):
    proyeccion_id: int
    ciclo_id: int
    version: str
    descripcion: Optional[str] = None
    status: str
    is_current: bool
    published_at: Optional[datetime] = None
    source_type: Optional[str] = None
    parent_version_id: Optional[int] = None

class ProyeccionPublishIn(BaseModel):
    sync_policy: SyncPolicy = Field(..., description="Política a aplicar al publish: none|sync|regen")

class ProyeccionReforecastIn(BaseModel):
    descripcion: Optional[str] = None

class ProyeccionLineaOut(BaseModel):
    proyeccion_linea_id: int
    semana_idx: int
    fecha_plan: date
    pp_g: float
    incremento_g_sem: Optional[float] = None
    sob_pct_linea: float
    cosecha_flag: bool
    retiro_org_m2: Optional[float] = None
    edad_dias: int
    nota: Optional[str] = None

class PublishResult(BaseModel):
    applied: bool = False
    sync_policy: SyncPolicy
    impact_summary: str
