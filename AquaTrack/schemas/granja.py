from pydantic import BaseModel
from typing import Optional

class GranjaCreate(BaseModel):
    nombre: str
    ubicacion: Optional[str] = None
    descripcion: Optional[str] = None
    superficie_total_m2: float

class GranjaOut(BaseModel):
    granja_id: int
    nombre: str
    ubicacion: Optional[str] = None
    descripcion: Optional[str] = None
    superficie_total_m2: float
