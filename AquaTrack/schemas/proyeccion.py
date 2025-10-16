# schemas/proyeccion.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
from datetime import date, datetime

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


class ProyeccionReforecastIn(BaseModel):
    descripcion: Optional[str] = None


class ImpactStats(BaseModel):
    updated: int = 0
    deleted: int = 0
    created: int = 0


class PublishResult(BaseModel):
    applied: bool = False
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


# --- Curvas objetivo (proyección desde planes/manual) ---

class CosechaFlagIn(BaseModel):
    semana_idx: int = Field(..., ge=0, description="Índice de semana donde hay cosecha.")
    retiro_org_m2: Optional[float] = Field(default=None, ge=0, description="Densidad a retirar en esta ola (opcional).")
    final: Optional[bool] = Field(default=None, description="Marca si esta es la ola final. Si es None, se inferirá si es la última flag.")


class CurvaConfig(BaseModel):
    semanas: int = Field(..., ge=1, description="Número total de semanas a proyectar.")
    peso_final_objetivo_g: float = Field(..., ge=0, description="PP objetivo al final de la serie (g).")
    sob_final_objetivo_pct: float = Field(..., ge=0, le=100, description="SOB objetivo al final de la serie (%).")
    shape: Literal["linear", "ease_in", "ease_out", "s_curve"] = Field(
        default="s_curve",
        description="Forma de la curva de crecimiento de PP."
    )
    pp_inicial_g: Optional[float] = Field(default=None, ge=0, description="Si no se envía, se toma de SiembraPlan.talla_inicial_g o 0.")


class ProyeccionFromPlansIn(BaseModel):
    """
    Genera una proyección a partir de la ventana de siembra y parámetros de curva.
    - Si use_existing_seeding_plan=True, usa SiembraPlan.ventana_fin como start_date
      y SiembraPlan.talla_inicial_g como pp_inicial_g cuando no se envían.
    - Si use_existing_harvest_plan=True y NO envías `cosechas`, derivamos flags desde CosechaOla:
      cada ola se marca en la semana más cercana a su ventana_fin y usa objetivo_retiro_org_m2.
      Si ola.tipo == 'f' se marca como final.
    - Si envías `cosechas`, éstas tienen prioridad sobre lo derivado del plan.
    """
    start_date: Optional[date] = None
    curva: CurvaConfig
    cosechas: Optional[List[CosechaFlagIn]] = None
    use_existing_seeding_plan: bool = True
    use_existing_harvest_plan: bool = True


class FromPlansResult(BaseModel):
    proyeccion_id: int
    ciclo_id: int
    lineas_insertadas: int
    status: str
    is_current: bool
    source_type: str
    warnings: List[str] = []


# --- NUEVO: Reforecast vivo manual ---

class ReforecastUpdateIn(BaseModel):
    event_date: Optional[date] = None
    pp_g: Optional[float] = Field(default=None, ge=0)
    sob_pct: Optional[float] = Field(default=None, ge=0, le=100)
    reason: Optional[str] = Field(default="manual")


class ReforecastUpdateOut(BaseModel):
    ciclo_id: int
    proyeccion_id: int
    week_idx: int
    event_date: date
    applied: bool
    anchors_applied: Dict[str, Any]
    lines_rebuilt: int
