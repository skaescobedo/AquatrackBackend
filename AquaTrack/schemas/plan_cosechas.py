from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from schemas.common import Timestamps


class PlanCosechasBase(BaseModel):
    ciclo_id: int
    proyeccion_id: int
    nota_operativa: Optional[str] = Field(None, max_length=255)


class PlanCosechasCreate(PlanCosechasBase):
    created_by: Optional[int] = None


class PlanCosechasUpdate(BaseModel):
    nota_operativa: Optional[str] = None


class PlanCosechasOut(PlanCosechasBase, Timestamps):
    plan_cosechas_id: int
    created_by: Optional[int]

    class Config:
        orm_mode = True
