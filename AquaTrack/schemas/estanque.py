from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from schemas.common import Timestamps
from schemas.enums import EstanqueStatusEnum


class EstanqueBase(BaseModel):
    granja_id: int
    nombre: str = Field(..., max_length=120)
    superficie_m2: float = Field(..., gt=0)
    status: EstanqueStatusEnum = EstanqueStatusEnum.i


class EstanqueCreate(EstanqueBase):
    pass


class EstanqueUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=120)
    superficie_m2: Optional[float] = Field(None, gt=0)
    status: Optional[EstanqueStatusEnum] = None


class EstanqueOut(EstanqueBase, Timestamps):
    estanque_id: int

    class Config:
        orm_mode = True
