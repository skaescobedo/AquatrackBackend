from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import date

class PlanCosechasUpsert(BaseModel):
    nota_operativa: Optional[str] = None

class PlanCosechasOut(BaseModel):
    plan_cosechas_id: int
    ciclo_id: int
    nota_operativa: Optional[str] = None

class CosechaOlaUpsert(BaseModel):
    nombre: str
    tipo: Literal["p", "f"]  # precosecha/final
    ventana_inicio: date
    ventana_fin: date
    objetivo_retiro_org_m2: Optional[float] = Field(default=None, ge=0)
    estado: Optional[Literal["p","r","x"]] = "p"
    orden: Optional[int] = None
    notas: Optional[str] = None

class CosechaOlaOut(BaseModel):
    cosecha_ola_id: int
    plan_cosechas_id: int
    nombre: str
    tipo: str
    ventana_inicio: date
    ventana_fin: date
    objetivo_retiro_org_m2: Optional[float] = None
    estado: str
    orden: Optional[int] = None
    notas: Optional[str] = None

class CosechaEstanqueOut(BaseModel):
    cosecha_estanque_id: int
    cosecha_ola_id: int
    estanque_id: int
    estado: str
    fecha_cosecha: date
    pp_g: Optional[float] = None
    biomasa_kg: Optional[float] = None
    densidad_retirada_org_m2: Optional[float] = None
    notas: Optional[str] = None

class CosechaReprogramIn(BaseModel):
    fecha_nueva: date
    motivo: Optional[str] = None

class CosechaConfirmIn(BaseModel):
    fecha_cosecha: date
    pp_g: float = Field(ge=0)
    biomasa_kg: Optional[float] = Field(default=None, ge=0)
    densidad_retirada_org_m2: Optional[float] = Field(default=None, ge=0)
    notas: Optional[str] = None

# >>> NUEVO: respuesta anidada ola + sus estanques
class CosechaOlaWithPondsOut(BaseModel):
    ola: CosechaOlaOut
    ponds: List[CosechaEstanqueOut]
