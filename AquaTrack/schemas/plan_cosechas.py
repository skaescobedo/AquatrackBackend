# schemas/plan_cosechas.py
from typing import Optional
from pydantic import BaseModel, Field
from schemas.common import Timestamps

class PlanCosechasBase(BaseModel):
    # ciclo_id viene del path; no se pide en payload
    nota_operativa: Optional[str] = Field(None, max_length=255)

class PlanCosechasCreate(PlanCosechasBase):
    # created_by lo fija el backend
    pass

class PlanCosechasUpdate(BaseModel):
    nota_operativa: Optional[str] = None

class PlanCosechasOut(PlanCosechasBase, Timestamps):
    plan_cosechas_id: int
    ciclo_id: int
    created_by: Optional[int]

    model_config = {"from_attributes": True}
