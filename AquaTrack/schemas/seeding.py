from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, Field, condecimal
from typing import List

# ---------- Plan ----------

class SeedingPlanCreate(BaseModel):
    ventana_inicio: date
    ventana_fin: date
    densidad_org_m2: condecimal(ge=0, max_digits=12, decimal_places=4)
    talla_inicial_g: condecimal(ge=0, max_digits=7, decimal_places=3)
    observaciones: str | None = None
    # Auto-creación: se genera siembra_estanque para TODOS los estanques vigentes y sin siembra asociada.


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
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Siembra por estanque ----------

class SeedingCreateForPond(BaseModel):
    fecha_tentativa: date | None = None
    lote: str | None = None
    densidad_override_org_m2: condecimal(gt=0, max_digits=12, decimal_places=4) | None = None
    talla_inicial_override_g: condecimal(gt=0, max_digits=7, decimal_places=3) | None = None
    observaciones: str | None = None


class SeedingReprogramIn(BaseModel):
    # Si vienen como null → no cambian. Si vienen con 0 → no cambian.
    # Cualquier otro valor válido → actualiza.
    fecha_nueva: date | None = None
    lote: str | None = None
    densidad_override_org_m2: condecimal(ge=0, max_digits=12, decimal_places=4) | None = None  # antes gt=0
    talla_inicial_override_g: condecimal(ge=0, max_digits=7, decimal_places=3) | None = None   # antes gt=0
    motivo: str | None = None


class SeedingFechaLogOut(BaseModel):
    siembra_fecha_log_id: int
    fecha_anterior: date | None
    fecha_nueva: date
    motivo: str | None
    changed_by: int
    changed_at: datetime

    class Config:
        from_attributes = True


class SeedingOut(BaseModel):
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
    updated_at: datetime

    class Config:
        from_attributes = True


class SeedingPlanWithItemsOut(SeedingPlanOut):
    siembras: List[SeedingOut]
