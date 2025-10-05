# schemas/common.py
from __future__ import annotations

from datetime import date, datetime
from typing import Generic, Mapping, Optional, Sequence, TypeVar

from pydantic import BaseModel, Field

# -------------------------------------------------------------------
# Compatibilidad Pydantic v1/v2 para modelos genéricos
# -------------------------------------------------------------------
try:
    # v1
    from pydantic.generics import GenericModel as _GenericModel  # type: ignore
except Exception:
    # v2
    from pydantic import BaseModel as _GenericModel  # type: ignore

# Pydantic v2 validator API
try:
    from pydantic import model_validator  # v2
except Exception:  # pragma: no cover
    # shim para v1: usaremos root_validator equivalente solo donde importe
    from pydantic import root_validator as model_validator  # type: ignore


# -------------------------------------------------------------------
# Importa enums compartidos (solo el SortOrder aquí)
# -------------------------------------------------------------------
from enums.enums import SortOrderEnum  # ASC / DESC


# -------------------------------------------------------------------
# Objetos de respuesta simples / mensajes
# -------------------------------------------------------------------
class Msg(BaseModel):
    """Respuesta simple con mensaje plano (útil para deletes, acciones, etc.)."""
    detail: str


class BulkResult(BaseModel):
    """Resultado estándar para operaciones masivas."""
    success: int = 0
    failed: int = 0


# -------------------------------------------------------------------
# Timestamps (solo para respuestas; no usarlos en creates)
# -------------------------------------------------------------------
class Timestamps(BaseModel):
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Permite construir desde objetos ORM (SQLAlchemy)
    model_config = {"from_attributes": True}


# -------------------------------------------------------------------
# Rango de fechas reutilizable
# Acepta tanto from_date/to_date (alias) como start_date/end_date
# y valida start_date <= end_date
# -------------------------------------------------------------------
class DateRange(BaseModel):
    start_date: date = Field(..., alias="from_date")
    end_date: date = Field(..., alias="to_date")

    # Permite que el cliente envíe start_date/end_date (por nombre)
    # o from_date/to_date (por alias)
    model_config = {
        "populate_by_name": True
    }

    @model_validator(mode="after")  # v2 (en v1 funciona por el shim)
    def validate_range(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date no puede ser mayor que end_date")
        return self


# -------------------------------------------------------------------
# Parámetros de paginación / ordenación comunes
# - Usa whitelist en el servicio con un mapa {api_field: ORM_column}
# -------------------------------------------------------------------
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=200)
    sort_by: Optional[str] = None         # nombre de columna expuesta por el endpoint
    sort_order: SortOrderEnum = SortOrderEnum.asc # ASC / DESC


# -------------------------------------------------------------------
# Respuesta paginada genérica (útil para listas)
# Nota: en v2 este GenericModel fallback funciona con _GenericModel
# -------------------------------------------------------------------
T = TypeVar("T")


class Paginated(_GenericModel, Generic[T]):  # type: ignore[misc]
    total: int
    page: int
    per_page: int
    items: Sequence[T]


# -------------------------------------------------------------------
# Identificador simple (útil para respuestas de creación)
# -------------------------------------------------------------------
class IdOut(BaseModel):
    id: int


# -------------------------------------------------------------------
# Metadata opcional para archivos subidos
# (si la expones desde servicios de upload)
# -------------------------------------------------------------------
class UploadedFileInfo(BaseModel):
    url: Optional[str] = None
    size_bytes: Optional[int] = None
    checksum: Optional[str] = None


# -------------------------------------------------------------------
# Filtros comunes por granja/ciclo para endpoints de listado
# -------------------------------------------------------------------
class GranjaCicloFilter(BaseModel):
    granja_id: Optional[int] = None
    ciclo_id: Optional[int] = None


# -------------------------------------------------------------------
# (Opcional) Ayudantes de tipado para servicios
# No se usan directamente por FastAPI, pero sirven de guía
# -------------------------------------------------------------------
class SortWhitelist(BaseModel):
    """
    Sugerencia de estructura para mapear `sort_by` -> columna ORM en el servicio.
    Ejemplo de uso en servicio:
        sort_map: dict[str, Any] = {
            "fecha": Biometria.fecha,
            "pp_g": Biometria.pp_g,
        }
    """
    mapping: Mapping[str, object] = Field(default_factory=dict)
