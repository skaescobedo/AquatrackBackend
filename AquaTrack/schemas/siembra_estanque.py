# schemas/siembra_estanque.py
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field
from schemas.common import Timestamps
from enums.enums import SiembraEstadoEnum


class SiembraEstanqueBase(BaseModel):
    # Entrada limpia: no siembra_plan_id, viene del contexto (ciclo->plan)
    estanque_id: int
    estado: SiembraEstadoEnum = SiembraEstadoEnum.p
    fecha_tentativa: Optional[date] = None
    fecha_siembra: Optional[date] = None
    lote: Optional[str] = Field(None, max_length=80)
    # Overrides editables (pueden quedar en NULL para heredar del plan)
    densidad_override_org_m2: Optional[float] = Field(None, ge=0)
    talla_inicial_override_g: Optional[float] = Field(None, ge=0)


class SiembraEstanqueCreate(SiembraEstanqueBase):
    # Sin created_by ni siembra_plan_id: los fija backend
    pass


class SiembraEstanqueUpdate(BaseModel):
    # 🔒 PATCH NO toca estado ni fecha_siembra (se hace en /confirmar)
    fecha_tentativa: Optional[date] = None
    densidad_override_org_m2: Optional[float] = Field(None, ge=0)
    talla_inicial_override_g: Optional[float] = Field(None, ge=0)
    lote: Optional[str] = Field(None, max_length=80)
    justificacion_cambio_fecha: Optional[str] = Field(
        None, description="Obligatoria si cambias fecha_tentativa"
    )


class SiembraEstanqueConfirm(BaseModel):
    """Payload explícito para confirmar una siembra."""
    fecha_siembra: date
    observaciones: Optional[str] = None
    justificacion_cambio_fecha: Optional[str] = None


class SiembraEstanqueOut(Timestamps, BaseModel):
    # Identidad y contexto
    siembra_estanque_id: int
    siembra_plan_id: int
    estanque_id: int
    created_by: Optional[int]

    # Estado/fechas
    estado: SiembraEstadoEnum
    fecha_tentativa: Optional[date] = None
    fecha_siembra: Optional[date] = None
    lote: Optional[str] = None

    # ✅ Valores EFECTIVOS “planos” para la UI
    densidad_org_m2: float
    talla_inicial_g: float

    # 👀 Overrides crudos (para edición/insight)
    #densidad_override_org_m2: Optional[float] = None
    #talla_inicial_override_g: Optional[float] = None

    model_config = {"from_attributes": True}
