from pydantic import BaseModel, condecimal
from typing import List
from .pond import PondCreate

class FarmBase(BaseModel):
    nombre: str
    ubicacion: str | None = None
    descripcion: str | None = None
    superficie_total_m2: condecimal(gt=-1, max_digits=14, decimal_places=2)

class FarmCreate(FarmBase):
    estanques: List[PondCreate] | None = None  # status se ignora y se fija a 'i' del lado servidor

class FarmUpdate(BaseModel):
    nombre: str | None = None
    ubicacion: str | None = None
    descripcion: str | None = None
    superficie_total_m2: condecimal(gt=-1, max_digits=14, decimal_places=2) | None = None
    is_active: bool | None = None

class FarmOut(FarmBase):
    granja_id: int
    is_active: bool

    class Config:
        from_attributes = True
