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


# ====== NUEVO: inputs para reprogramar y confirmar ======

class HarvestReprogramIn(BaseModel):
    fecha_nueva: date
    motivo: str | None = Field(None, max_length=255)


class HarvestConfirmIn(BaseModel):
    # Al menos uno de estos dos debe venir; si viene uno, el otro se deriva usando el PP vigente y área del estanque.
    biomasa_kg: condecimal(ge=0, max_digits=14, decimal_places=3) | None = None
    densidad_retirada_org_m2: condecimal(ge=0, max_digits=12, decimal_places=4) | None = None
    notas: str | None = Field(None, max_length=255)

    @model_validator(mode="after")
    def _at_least_one(self):
        if self.biomasa_kg is None and self.densidad_retirada_org_m2 is None:
            raise ValueError("Debes proporcionar biomasa_kg o densidad_retirada_org_m2.")
        return self
