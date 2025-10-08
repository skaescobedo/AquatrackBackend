from pydantic import BaseModel
from typing import Optional

class EstanqueCreate(BaseModel):
    granja_id: int
    nombre: str
    superficie_m2: float
    status: str = "i"

class EstanqueOut(BaseModel):
    estanque_id: int
    granja_id: int
    nombre: str
    superficie_m2: float
    status: str
