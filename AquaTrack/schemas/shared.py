# schemas/shared.py
from __future__ import annotations

from typing import Generic, Iterable, List, Optional, TypeVar
from pydantic import BaseModel, Field, constr

# -------------------------------------------------------------------
# Base común para todos los schemas (Pydantic v2)
# -------------------------------------------------------------------
class ORMModel(BaseModel):
    """
    Modelo base para schemas.
    - from_attributes=True: permite construir el schema desde objetos ORM.
    - populate_by_name=True: habilita usar 'alias' si decides nombrar distinto.
    - str_strip_whitespace=True: limpia espacios en strings.
    """
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "str_strip_whitespace": True,
    }


# -------------------------------------------------------------------
# Tipos compartidos (opcional)
# -------------------------------------------------------------------
# Útil para tu convención de estados de un solo carácter (p. ej., 'a', 'b', 'c')
EstadoChar = constr(strip_whitespace=True, min_length=1, max_length=1)


# -------------------------------------------------------------------
# Paginación reutilizable
# -------------------------------------------------------------------
T = TypeVar("T")

class PageMeta(ORMModel):
    """
    Metadatos de paginación.
    """
    page: int = Field(1, ge=1, description="Página actual.")
    size: int = Field(50, ge=1, le=500, description="Tamaño de página.")
    total_items: int = Field(..., ge=0, description="Total de elementos.")
    total_pages: int = Field(..., ge=0, description="Total de páginas.")

class Page(ORMModel, Generic[T]):
    """
    Envoltorio de resultados paginados.
    """
    items: List[T]
    meta: PageMeta

    @classmethod
    def from_items(
        cls,
        items: Iterable[T],
        page: int,
        size: int,
        total_items: int
    ) -> "Page[T]":
        total_pages = (total_items + size - 1) // size if size > 0 else 0
        return cls(
            items=list(items),
            meta=PageMeta(
                page=page,
                size=size,
                total_items=total_items,
                total_pages=total_pages,
            ),
        )


# -------------------------------------------------------------------
# Re-exports opcionales para imports más limpios
# -------------------------------------------------------------------
__all__ = [
    "ORMModel",
    "EstadoChar",
    "PageMeta",
    "Page",
]
