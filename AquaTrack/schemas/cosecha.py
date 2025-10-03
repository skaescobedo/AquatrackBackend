from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from decimal import Decimal

class CosechaOlaOut(BaseModel):
    cosecha_ola_id: int
    plan_cosechas_id: int
    nombre: str
    tipo: str
    ventana_inicio: date
    ventana_fin: date
    objetivo_retiro_org_m2: Optional[Decimal]
    estado: str
    orden: Optional[int]
    notas: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CosechaOlaCreate(BaseModel):
    plan_cosechas_id: int
    nombre: str
    tipo: str
    ventana_inicio: date
    ventana_fin: date
    objetivo_retiro_org_m2: Optional[Decimal] = None
    notas: Optional[str] = None
    created_by: Optional[int] = None

class CosechaOlaUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    ventana_inicio: Optional[date] = None
    ventana_fin: Optional[date] = None
    objetivo_retiro_org_m2: Optional[Decimal] = None
    estado: Optional[str] = None
    orden: Optional[int] = None
    notas: Optional[str] = None


class CosechaEstanqueOut(BaseModel):
    cosecha_estanque_id: int
    estanque_id: int
    cosecha_ola_id: int
    tipo: str
    estado: str
    fecha_cosecha: date
    pp_g: Optional[Decimal]
    biomasa_kg: Optional[Decimal]
    densidad_retirada_org_m2: Optional[Decimal]
    notas: Optional[str]
    confirmado_por: Optional[int]
    confirmado_event_at: Optional[datetime]
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CosechaEstanqueCreate(BaseModel):
    estanque_id: int
    cosecha_ola_id: int
    tipo: str
    fecha_cosecha: date
    pp_g: Optional[Decimal] = None
    biomasa_kg: Optional[Decimal] = None
    densidad_retirada_org_m2: Optional[Decimal] = None
    notas: Optional[str] = None
    created_by: int

class CosechaEstanqueUpdate(BaseModel):
    tipo: Optional[str] = None
    estado: Optional[str] = None
    fecha_cosecha: Optional[date] = None
    pp_g: Optional[Decimal] = None
    biomasa_kg: Optional[Decimal] = None
    densidad_retirada_org_m2: Optional[Decimal] = None
    notas: Optional[str] = None
    confirmado_por: Optional[int] = None
    confirmado_event_at: Optional[datetime] = None
