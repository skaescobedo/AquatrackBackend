from typing import Optional
from pydantic import BaseModel, Field
from schemas.common import Timestamps
from enums.enums import EstanqueStatusEnum

class EstanqueBase(BaseModel):
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
    granja_id: int  # <- se mantiene para que el front sepa a qué granja pertenece

    model_config = {"from_attributes": True}
