from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class PlanCosechasBase(BaseModel):
    ciclo_id: int
    proyeccion_id: int
    nota_operativa: Optional[str]


class PlanCosechasCreate(PlanCosechasBase):
    created_by: Optional[int]


class PlanCosechasOut(PlanCosechasBase):
    plan_cosechas_id: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
