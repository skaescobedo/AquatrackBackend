from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

class FechasOut(BaseModel):
    inicio: date
    hoy: date

class KpiSampleSizes(BaseModel):
    ponds_total: int
    ponds_with_density: int
    ponds_with_org_vivos: int

class SiembrasCounts(BaseModel):
    confirmadas: int
    total: int

class CosechasCounts(BaseModel):
    estanques_con_planeacion: int
    estanques_con_confirmada: int

class KPIOut(BaseModel):
    biomasa_estim_kg: float = 0.0
    densidad_viva_org_m2: float | None = None
    sob_vigente_prom_pct: Optional[float] = None
    pp_vigente_prom_g: Optional[float] = None
    sample_sizes: KpiSampleSizes
    siembras_avance_pct: Optional[float] = None
    cosechas_avance_pct: Optional[float] = None
    siembras_counts: SiembrasCounts
    cosechas_counts: CosechasCounts

class OlaProximaOut(BaseModel):
    ola_id: int
    nombre: str
    tipo: str  # 'p' | 'f'
    ventana_inicio: date
    ventana_fin: date
    pendientes: int

class AlertaOut(BaseModel):
    severity: str  # 'high' | 'med' | 'low'
    code: str
    estanque_id: Optional[int] = None
    dias: Optional[int] = None
    desvio_pct: Optional[float] = None
    msg: str

class PondRowOut(BaseModel):
    estanque_id: int
    nombre: str
    superficie_m2: float
    densidad_base_org_m2: float
    densidad_retirada_acum_org_m2: float
    densidad_viva_org_m2: float | None = None
    sob_vigente_pct: Optional[float] = None
    sob_fuente: Optional[str] = None
    pp_vigente_g: Optional[float] = None
    pp_fuente: Optional[str] = None
    pp_updated_at: Optional[datetime] = None
    org_vivos_est: Optional[float] = None
    biomasa_est_kg: Optional[float] = None

class ProyeccionSemanaOut(BaseModel):
    semana_idx: int
    fecha_plan: date
    pp_g: float
    sob_pct_linea: float

class OperationalStateOut(BaseModel):
    ciclo_id: int
    fechas: FechasOut
    kpi: KPIOut
    olas_proximas: List[OlaProximaOut]
    alertas: List[AlertaOut]
    por_estanque: List[PondRowOut]
    proyeccion_semana: Optional[ProyeccionSemanaOut] = None
