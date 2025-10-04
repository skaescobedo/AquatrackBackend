from __future__ import annotations

from datetime import date, datetime
from typing import Generic, List, Optional, Sequence, TypeVar

from pydantic import BaseModel, Field, root_validator

from .enums import SortOrderEnum


# -------------------------------------------------------------------
# Objetos de respuesta simples / mensajes
# -------------------------------------------------------------------
class Msg(BaseModel):
    detail: str


class BulkResult(BaseModel):
    success: int = 0
    failed: int = 0


# -------------------------------------------------------------------
# Timestamps (para respuestas; no los uses en creates)
# -------------------------------------------------------------------
class Timestamps(BaseModel):
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# -------------------------------------------------------------------
# Rango de fechas reutilizable (validación start <= end)
# -------------------------------------------------------------------
class DateRange(BaseModel):
    start_date: date = Field(..., alias="from_date")
    end_date: date = Field(..., alias="to_date")

    @root_validator
    def _check_range(cls, values):
        start = values.get("start_date")
        end = values.get("end_date")
        if start and end and start > end:
            raise ValueError("start_date no puede ser mayor que end_date")
        return values


# -------------------------------------------------------------------
# Parámetros de paginación / ordenación comunes
# -------------------------------------------------------------------
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=200)
    sort_by: Optional[str] = None  # nombre de columna expuesta por el endpoint
    sort_order: SortOrderEnum = SortOrderEnum.ASC


T = TypeVar("T")


# Respuesta paginada genérica (útil para listas)
# Nota: usa pydantic.generics.GenericModel en Pydantic v1
try:
    from pydantic.generics import GenericModel  # type: ignore
except Exception:
    # En Pydantic v2, GenericModel está en pydantic
    from pydantic import BaseModel as GenericModel  # fallback


class Paginated(GenericModel, Generic[T]):
    total: int
    page: int
    per_page: int
    items: Sequence[T]


# -------------------------------------------------------------------
# Identificadores comunes (útiles para respuestas de creación)
# -------------------------------------------------------------------
class IdOut(BaseModel):
    id: int


# -------------------------------------------------------------------
# Campos comunes para subida de archivos (opcionales)
# -------------------------------------------------------------------
class UploadedFileInfo(BaseModel):
    # Para devolver metadata adicional tras upload si la manejas en servicios
    url: Optional[str] = None
    size_bytes: Optional[int] = None
    checksum: Optional[str] = None


# -------------------------------------------------------------------
# Filtros comunes por granja/ciclo (para endpoints de listado)
# -------------------------------------------------------------------
class GranjaCicloFilter(BaseModel):
    granja_id: Optional[int] = None
    ciclo_id: Optional[int] = None
