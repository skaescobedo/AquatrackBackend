from pydantic import BaseModel, Field, condecimal

class PondBase(BaseModel):
    nombre: str
    superficie_m2: condecimal(gt=0, max_digits=14, decimal_places=2)
    is_vigente: bool = True

class PondCreate(PondBase):
    """No incluye 'status'; el backend lo fija siempre a 'i'."""

class PondUpdate(BaseModel):
    nombre: str | None = None
    superficie_m2: condecimal(gt=0, max_digits=14, decimal_places=2) | None = None
    is_vigente: bool | None = None

class PondOut(PondBase):
    estanque_id: int
    granja_id: int
    status: str  # i/a/c/m (solo lectura)

    class Config:
        from_attributes = True
