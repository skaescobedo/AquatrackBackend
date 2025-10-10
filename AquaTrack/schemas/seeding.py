from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class SiembraPlanUpsert(BaseModel):
    ventana_inicio: date
    ventana_fin: date
    densidad_org_m2: float = Field(ge=0)
    talla_inicial_g: float = Field(ge=0)
    observaciones: Optional[str] = None

class SiembraPlanOut(BaseModel):
    siembra_plan_id: int
    ciclo_id: int
    ventana_inicio: date
    ventana_fin: date
    densidad_org_m2: float
    talla_inicial_g: float
    observaciones: Optional[str] = None

class SiembraEstanqueOut(BaseModel):
    siembra_estanque_id: int
    siembra_plan_id: int
    estanque_id: int
    estado: str
    fecha_tentativa: Optional[date] = None
    fecha_siembra: Optional[date] = None
    lote: Optional[str] = None
    densidad_override_org_m2: Optional[float] = None
    talla_inicial_override_g: Optional[float] = None
    observaciones: Optional[str] = None

class ReprogramIn(BaseModel):
    fecha_nueva: date
    motivo: Optional[str] = None

class ConfirmIn(BaseModel):
    fecha_siembra: date
    lote: Optional[str] = None
    # Overrides: > 0 si se envían; None para no setear/limpiar
    densidad_override_org_m2: Optional[float] = Field(default=None, gt=0)
    talla_inicial_override_g: Optional[float] = Field(default=None, gt=0)
    observaciones: Optional[str] = None

class SiembraEstanqueOverrideIn(BaseModel):
    # Usa este schema en PATCH /siembra/ponds/{id} para setear/limpiar overrides
    densidad_override_org_m2: Optional[float] = Field(default=None, gt=0)
    talla_inicial_override_g: Optional[float] = Field(default=None, gt=0)
    lote: Optional[str] = None
    observaciones: Optional[str] = None
