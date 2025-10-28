from __future__ import annotations
from pydantic import BaseModel, Field, condecimal
from datetime import date, datetime
from typing import List


# ---------- IN ----------
class SeedingPlanCreate(BaseModel):
    ventana_inicio: date
    ventana_fin: date
    densidad_org_m2: condecimal(ge=0, max_digits=12, decimal_places=4)
    talla_inicial_g: condecimal(ge=0, max_digits=7, decimal_places=3)
    observaciones: str | None = None
    # auto-fill:
    autofill: bool = True  # si True, crear siembras para todos los estanques vigentes sin siembra en el plan


class SeedingPondCreate(BaseModel):
    fecha_tentativa: date | None = None
    lote: str | None = None
    densidad_override_org_m2: condecimal(ge=0, max_digits=12, decimal_places=4) | None = None
    talla_inicial_override_g: condecimal(ge=0, max_digits=7, decimal_places=3) | None = None
    observaciones: str | None = None


class SeedingPondReprogram(BaseModel):
    fecha_nueva: date
    motivo: str | None = None


# ---------- OUT ----------
class SeedingPondOut(BaseModel):
    siembra_estanque_id: int
    siembra_plan_id: int
    estanque_id: int
    status: str
    fecha_tentativa: date | None
    fecha_siembra: date | None
    lote: str | None
    densidad_override_org_m2: float | None
    talla_inicial_override_g: float | None
    observaciones: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class SeedingPlanOut(BaseModel):
    siembra_plan_id: int
    ciclo_id: int
    ventana_inicio: date
    ventana_fin: date
    densidad_org_m2: float
    talla_inicial_g: float
    status: str
    observaciones: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class SeedingPlanDetailOut(SeedingPlanOut):
    siembras: List[SeedingPondOut]
