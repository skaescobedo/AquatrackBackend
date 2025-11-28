# schemas/pond.py
from pydantic import BaseModel, condecimal


class PondBase(BaseModel):
    nombre: str
    superficie_m2: condecimal(gt=0, max_digits=14, decimal_places=2)
    is_vigente: bool = True


class PondCreate(PondBase):
    """No incluye 'status'; el backend lo fija siempre a 'i'."""


class PondUpdate(BaseModel):
    """
    Schema para actualizar estanque.

    - is_vigente se gestiona automáticamente (no editable)
    - Versionamiento automático si cambia superficie_m2 y tiene historial
    """
    nombre: str | None = None
    superficie_m2: condecimal(gt=0, max_digits=14, decimal_places=2) | None = None
    notas: str | None = None


class PondOut(PondBase):
    estanque_id: int
    granja_id: int
    status: str  # i/a/c/m (solo lectura)
    notas: str | None = None

    class Config:
        from_attributes = True