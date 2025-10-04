from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class EstanqueBase(BaseModel):
    granja_id: int
    nombre: str = Field(..., max_length=120)
    superficie_m2: float = Field(..., gt=0)
    status: str = Field(default='i', pattern='^[iacm]$')  # i=inactive, a=active, c=closed, m=maintenance


class EstanqueCreate(EstanqueBase):
    pass


class EstanqueUpdate(BaseModel):
    nombre: Optional[str]
    superficie_m2: Optional[float] = Field(None, gt=0)
    status: Optional[str] = Field(None, pattern='^[iacm]$')


class EstanqueOut(EstanqueBase):
    estanque_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
