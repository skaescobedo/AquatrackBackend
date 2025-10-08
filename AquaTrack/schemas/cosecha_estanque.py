# schemas/cosecha_estanque.py
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field
from enums.enums import CosechaEstadoDetEnum
from schemas.common import Timestamps

class CosechaEstanqueBase(BaseModel):
    # cosecha_ola_id viene del path al crear (si anidas rutas)
    estanque_id: int
    # Estado se define como pendiente en creación; confirmar con endpoint dedicado
    estado: CosechaEstadoDetEnum = CosechaEstadoDetEnum.p
    # Fecha programada (tentativa); la real se fija al confirmar
    fecha_cosecha: date
    pp_g: Optional[float] = Field(None, ge=0)
    biomasa_kg: Optional[float] = Field(None, ge=0)
    densidad_retirada_org_m2: Optional[float] = Field(None, ge=0)
    notas: Optional[str] = Field(None, max_length=255)

class CosechaEstanqueCreate(CosechaEstanqueBase):
    # created_by/confirmado_por los fija backend
    pass

class CosechaEstanqueUpdate(BaseModel):
    # PATCH NO debe cambiar `estado` ni confirmar; eso va en /confirmar
    fecha_cosecha: Optional[date] = None
    pp_g: Optional[float] = Field(None, ge=0)
    biomasa_kg: Optional[float] = Field(None, ge=0)
    densidad_retirada_org_m2: Optional[float] = Field(None, ge=0)
    notas: Optional[str] = Field(None, max_length=255)
    # exige justificación si cambias fecha programada -> genera CosechaFechaLog
    justificacion_cambio_fecha: Optional[str] = Field(
        None, description="Obligatoria si cambias fecha_cosecha (programada)"
    )

class CosechaEstanqueConfirm(BaseModel):
    """Payload para confirmar la cosecha (fija fecha real y métricas)."""
    fecha_cosecha: date
    pp_g: Optional[float] = Field(None, ge=0)
    biomasa_kg: Optional[float] = Field(None, ge=0)
    densidad_retirada_org_m2: Optional[float] = Field(None, ge=0)
    notas: Optional[str] = Field(None, max_length=255)
    justificacion_cambio_fecha: Optional[str] = Field(
        None, description="Se registra si la fecha real difiere de la programada"
    )

class CosechaEstanqueOut(CosechaEstanqueBase, Timestamps):
    cosecha_estanque_id: int
    cosecha_ola_id: int
    created_by: Optional[int]
    confirmado_por: Optional[int]
    confirmado_event_at: Optional[datetime]

    model_config = {"from_attributes": True}
