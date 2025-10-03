from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date

class PlanCosechasOut(BaseModel):
    plan_cosechas_id: int
    ciclo_id: int
    proyeccion_id: int
    nombre: str
    fecha_inicio_plan: date
    fecha_fin_plan: date
    nota_operativa: Optional[str]
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PlanCosechasCreate(BaseModel):
    ciclo_id: int
    proyeccion_id: int
    nombre: str
    fecha_inicio_plan: date
    fecha_fin_plan: date
    nota_operativa: Optional[str] = None
    created_by: int

class PlanCosechasUpdate(BaseModel):
    nombre: Optional[str] = None
    fecha_inicio_plan: Optional[date] = None
    fecha_fin_plan: Optional[date] = None
    nota_operativa: Optional[str] = None
