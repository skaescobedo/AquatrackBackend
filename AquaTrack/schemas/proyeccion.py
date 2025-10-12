# /schemas/proyeccion.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import date, datetime

SyncPolicy = Literal["none", "sync", "regen"]


class ProyeccionFromFileIn(BaseModel):
    archivo_id: int = Field(..., ge=1)
    force_reingest: bool = False  # si ya existe vínculo por checksum+cycle, reintenta


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


class ProyeccionPublishIn(BaseModel):
    sync_policy: SyncPolicy = Field(..., description="Política a aplicar al publish: none|sync|regen")


class ProyeccionReforecastIn(BaseModel):
    descripcion: Optional[str] = None


class ImpactStats(BaseModel):
    updated: int = 0
    deleted: int = 0
    created: int = 0


class PublishResult(BaseModel):
    applied: bool = False
    sync_policy: SyncPolicy
    impact_summary: str
    seeding_locked: bool
    seeding_stats: ImpactStats
    harvest_stats: ImpactStats


class FromFileResult(BaseModel):
    proyeccion_id: int
    ciclo_id: int
    lineas_insertadas: int
    status: str
    is_current: bool
    source_type: str
    warnings: List[str] = []
