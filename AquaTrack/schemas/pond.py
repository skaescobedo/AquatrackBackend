from pydantic import BaseModel, Field, condecimal


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
    - requires_new_version: confirma creación de nueva versión al cambiar superficie_m2
    """
    nombre: str | None = None
    superficie_m2: condecimal(gt=0, max_digits=14, decimal_places=2) | None = None
    notas: str | None = None
    requires_new_version: bool = Field(
        default=False,
        description="Confirma creación de nueva versión si se cambia superficie_m2"
    )


class PondOut(PondBase):
    estanque_id: int
    granja_id: int
    status: str  # i/a/c/m (solo lectura)
    notas: str | None = None

    class Config:
        from_attributes = True