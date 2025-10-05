# services/common.py
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence, TypeVar, Union, overload

import sqlalchemy as sa
from sqlalchemy import func, literal
from sqlalchemy.orm import Query, Session
from sqlalchemy.sql import Select

from enums.enums import SortOrderEnum
from schemas.common import PaginationParams, Paginated, DateRange

T = TypeVar("T")


# -------------------------------------------------------------------
# Ordenamiento
# -------------------------------------------------------------------
def _normalize_sort_order(value: str | SortOrderEnum | None) -> SortOrderEnum:
    if value is None:
        return SortOrderEnum.ASC
    if isinstance(value, SortOrderEnum):
        return value
    return SortOrderEnum.DESC if value.lower() == "desc" else SortOrderEnum.ASC


def _resolve_sort_column(sort_by: str | None, sort_map: Mapping[str, Any]) -> Any | None:
    if not sort_by:
        return None
    # sort_map: {"campo_api": Modelo.columna | expresión_sqlalchemy}
    return sort_map.get(sort_by)


def _apply_nulls_last(expr: Any, order: SortOrderEnum, dialect_name: str) -> Any:
    """
    Forzar NULLS LAST de forma portable. MySQL no soporta NULLS LAST explícito.
    Truco: ordenar por expresión IS NULL y luego por la columna.
    """
    if dialect_name.startswith("mysql"):
        # En MySQL: primero los no-null, luego null => (col IS NULL) asc/desc
        nulls_key = expr.is_(None)
        if order == SortOrderEnum.DESC:
            return sa.desc(nulls_key), sa.desc(expr)
        return sa.asc(nulls_key), sa.asc(expr)
    # Dialectos que soportan nulls_last()
    return (sa.nulls_last(sa.desc(expr)) if order == SortOrderEnum.DESC
            else sa.nulls_last(sa.asc(expr)),)


def apply_sorting(
    source: Union[Query, Select],
    sort_by: str | None,
    sort_order: str | SortOrderEnum | None,
    sort_map: Mapping[str, Any],
) -> Union[Query, Select]:
    """
    Aplica ordenamiento seguro usando un mapa de columnas permitidas.
    - `sort_map` debe mapear nombres expuestos por el API a columnas/expresiones SQLAlchemy.
    """
    column = _resolve_sort_column(sort_by, sort_map)
    if column is None:
        return source

    order = _normalize_sort_order(sort_order)
    dialect_name = (
        source.session.bind.dialect.name  # type: ignore[attr-defined]
        if isinstance(source, Query) and source.session and source.session.bind
        else getattr(getattr(source, "_execution_options", None), "get", lambda *_: None)("dialect", None) or "mysql"
    )

    order_by_parts = _apply_nulls_last(column, order, dialect_name)

    if isinstance(source, Query):
        return source.order_by(*order_by_parts)  # type: ignore[arg-type]
    else:
        return source.order_by(*order_by_parts)  # Select


# -------------------------------------------------------------------
# Paginación
# -------------------------------------------------------------------
def apply_pagination(
    source: Union[Query, Select],
    page: int,
    per_page: int,
) -> Union[Query, Select]:
    """
    Aplica offset/limit de forma uniforme a Query/Select.
    """
    offset = (page - 1) * per_page
    if isinstance(source, Query):
        return source.offset(offset).limit(per_page)
    return source.offset(offset).limit(per_page)


# -------------------------------------------------------------------
# Conteo total (eficiente)
# -------------------------------------------------------------------
def count_total(db: Session, source: Union[Query, Select]) -> int:
    """
    Devuelve el total de filas para la consulta *sin* el limit/offset.
    - Para Query: usa count() sin order_by para acelerar.
    - Para Select: lo envuelve como subquery y cuenta.
    """
    if isinstance(source, Query):
        # Elimina order_by para que el COUNT sea más barato
        return source.order_by(None).count()
    else:
        # SELECT COUNT(*) FROM ( <stmt sin limit/offset> ) AS anon_1
        base = source
        # SQLAlchemy asegura que .limit/.offset en subquery no afecten el count real.
        subq = base.order_by(None).options().subquery()
        stmt_count = sa.select(func.count(literal(1))).select_from(subq)
        return db.execute(stmt_count).scalar_one()


# -------------------------------------------------------------------
# Materialización de resultados
# -------------------------------------------------------------------
def fetch_all(db: Session, source: Union[Query, Select]) -> list[Any]:
    if isinstance(source, Query):
        return source.all()
    result = db.execute(source)
    # Si viene de ORM select(Model), usar scalars() para instancias
    try:
        return result.scalars().all()
    except Exception:
        return result.all()


# -------------------------------------------------------------------
# Combo de paginación completa (items + total + envoltura Paginated[T])
# -------------------------------------------------------------------
def paginate_and_respond(
    db: Session,
    base_source: Union[Query, Select],
    params: PaginationParams,
    sort_map: Mapping[str, Any] | None = None,
) -> Paginated[Any]:
    """
    Aplica (opcionalmente) ordenamiento seguro, luego paginación y construye Paginated[T].
    """
    source = base_source
    if sort_map:
        source = apply_sorting(source, params.sort_by, params.sort_order, sort_map)

    total = count_total(db, source)
    page_slice = apply_pagination(source, params.page, params.per_page)
    items = fetch_all(db, page_slice)

    return Paginated[Any](
        total=total,
        page=params.page,
        per_page=params.per_page,
        items=items,
    )


# -------------------------------------------------------------------
# Filtros utilitarios
# -------------------------------------------------------------------
def apply_date_range_filter(
    column: Any,
    date_range: DateRange | None,
    inclusive: bool = True,
) -> Any | None:
    """
    Construye una condición SQLAlchemy para un rango de fechas.
    - inclusive=True => BETWEEN inclusivo
    - inclusive=False => [from, to) (incluye inicio, excluye fin)
    """
    if not date_range:
        return None

    start = date_range.start_date
    end = date_range.end_date

    if inclusive:
        conds = []
        if start:
            conds.append(column >= start)
        if end:
            conds.append(column <= end)
        return sa.and_(*conds) if conds else None
    else:
        conds = []
        if start:
            conds.append(column >= start)
        if end:
            conds.append(column < end)
        return sa.and_(*conds) if conds else None


def ilike_any(column: Any, terms: Iterable[str] | None) -> Any | None:
    """
    Devuelve un OR de ILIKE para cualquier término (útil para búsquedas simples).
    En MySQL se traduce a LIKE case-insensitive según collation.
    """
    if not terms:
        return None
    patterns = [f"%{t.strip()}%" for t in terms if t and t.strip()]
    if not patterns:
        return None
    return sa.or_(*[column.ilike(p) for p in patterns])  # type: ignore[attr-defined]


# -------------------------------------------------------------------
# Helpers de uso rápido en servicios
# -------------------------------------------------------------------
def apply_common_list_ops(
    db: Session,
    base_source: Union[Query, Select],
    params: PaginationParams,
    sort_map: Mapping[str, Any] | None = None,
    extra_filters: Sequence[Any] | None = None,
) -> Paginated[Any]:
    """
    Aplica filtros adicionales, ordena (si se indica), pagina y retorna Paginated.
    """
    source = base_source
    if extra_filters:
        if isinstance(source, Query):
            for f in extra_filters:
                if f is not None:
                    source = source.filter(f)
        else:
            # Select
            for f in extra_filters:
                if f is not None:
                    source = source.where(f)

    return paginate_and_respond(db, source, params, sort_map=sort_map)


# -------------------------------------------------------------------
# Ejemplos de uso (comentados)
# -------------------------------------------------------------------
# def listar_biometrias(db: Session, filtros: BiometriaFilter, pag: PaginationParams):
#     from models.biometria import Biometria
#
#     stmt = sa.select(Biometria)  # estilo 2.0
#     extra = []
#
#     # Filtro por ciclo/estanque si vienen
#     if filtros.ciclo_id:
#         extra.append(Biometria.ciclo_id == filtros.ciclo_id)
#     if filtros.estanque_id:
#         extra.append(Biometria.estanque_id == filtros.estanque_id)
#
#     # Rango de fechas (inclusive)
#     dr = apply_date_range_filter(Biometria.fecha, filtros.date_range)
#     if dr is not None:
#         extra.append(dr)
#
#     # Búsqueda por notas
#     search = ilike_any(Biometria.notas, filtros.search_terms)
#     if search is not None:
#         extra.append(search)
#
#     # Mapa de orden permitido (clave expuesta -> columna)
#     sort_map = {
#         "fecha": Biometria.fecha,
#         "pp_g": Biometria.pp_g,
#         "sob": Biometria.sob_usada_pct,
#     }
#
#     return apply_common_list_ops(db, stmt, pag, sort_map=sort_map, extra_filters=extra)
