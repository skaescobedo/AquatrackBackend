from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from decimal import Decimal

class SiembraPlanOut(BaseModel):
    siembra_plan_id: int
    ciclo_id: int
    fecha_inicio_plan: date
    fecha_fin_plan: Optional[date]
    descripcion: Optional[str]
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SiembraPlanCreate(BaseModel):
    ciclo_id: int
    fecha_inicio_plan: date
    fecha_fin_plan: Optional[date] = None
    descripcion: Optional[str] = None
    created_by: int

class SiembraPlanUpdate(BaseModel):
    fecha_inicio_plan: Optional[date] = None
    fecha_fin_plan: Optional[date] = None
    descripcion: Optional[str] = None


class SiembraEstanqueOut(BaseModel):
    siembra_estanque_id: int
    estanque_id: int
    siembra_plan_id: int
    fecha_siembra: date
    cantidad_postlarvas: int
    densidad_org_m2: Decimal
    origen_postlarvas: Optional[str]
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True

class SiembraEstanqueCreate(BaseModel):
    estanque_id: int
    siembra_plan_id: int
    fecha_siembra: date
    cantidad_postlarvas: int
    densidad_org_m2: Decimal
    origen_postlarvas: Optional[str] = None
    created_by: int

class SiembraEstanqueUpdate(BaseModel):
    fecha_siembra: Optional[date] = None
    cantidad_postlarvas: Optional[int] = None
    densidad_org_m2: Optional[Decimal] = None
    origen_postlarvas: Optional[str] = None
