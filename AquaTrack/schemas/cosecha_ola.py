# schemas/cosecha_ola.py
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field
from enums.enums import CosechaTipoEnum, CosechaEstadoEnum
from schemas.common import Timestamps

class CosechaOlaBase(BaseModel):
    # plan_cosechas_id viene del contexto (ruta), no en payload
    nombre: str = Field(..., max_length=120)
    tipo: CosechaTipoEnum
    ventana_inicio: date
    ventana_fin: date
    objetivo_retiro_org_m2: Optional[float] = Field(None, ge=0)
    estado: CosechaEstadoEnum = CosechaEstadoEnum.p
    orden: Optional[int] = None
    notas: Optional[str] = Field(None, max_length=255)

class CosechaOlaCreate(CosechaOlaBase):
    # created_by lo fija el backend
    pass

class CosechaOlaUpdate(BaseModel):
    # Mantén PATCH solo para ventana/notas; los cambios de estado via endpoints dedicados
    ventana_inicio: Optional[date] = None
    ventana_fin: Optional[date] = None
    notas: Optional[str] = None
    # si prefieres permitir cambiar estado por PATCH, vuelve a añadir:
    # estado: Optional[CosechaEstadoEnum] = None

class CosechaOlaOut(CosechaOlaBase, Timestamps):
    cosecha_ola_id: int
    plan_cosechas_id: int
    created_by: Optional[int]

    model_config = {"from_attributes": True}
