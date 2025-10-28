# schemas/harvest.py
from __future__ import annotations
from datetime import date, datetime
from typing import Literal, Optional, List
from pydantic import BaseModel, Field, condecimal, model_validator


class HarvestWaveCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    tipo: Literal["p", "f"] = Field(..., description="p=parcial, f=final")
    ventana_inicio: date
    ventana_fin: date
    objetivo_retiro_org_m2: condecimal(ge=0, max_digits=12, decimal_places=4) | None = None
    orden: int | None = None
    notas: str | None = Field(None, max_length=255)

    @model_validator(mode="after")
    def _check_window(self):
        if self.ventana_inicio > self.ventana_fin:
            raise ValueError("ventana_inicio no puede ser mayor a ventana_fin")
        return self


class HarvestWaveOut(BaseModel):
    cosecha_ola_id: int
    ciclo_id: int
    nombre: str
    tipo: str
    ventana_inicio: date
    ventana_fin: date
    objetivo_retiro_org_m2: float | None
    status: str
    orden: int | None
    notas: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HarvestEstanqueOut(BaseModel):
    cosecha_estanque_id: int
    cosecha_ola_id: int
    estanque_id: int
    status: str
    fecha_cosecha: date
    pp_g: float | None
    biomasa_kg: float | None
    densidad_retirada_org_m2: float | None
    notas: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HarvestWaveWithItemsOut(HarvestWaveOut):
    cosechas: List[HarvestEstanqueOut]
