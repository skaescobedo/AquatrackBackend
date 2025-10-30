# api/analytics.py
"""
Endpoints de analytics para dashboards y reportes.
"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session
from typing import Dict, Any

from utils.db import get_db
from utils.dependencies import get_current_user
from models.user import Usuario

from services.analytics_service import (
    get_cycle_overview,
    get_pond_detail
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ==========================================
# GET - Dashboard General del Ciclo
# ==========================================

@router.get(
    "/cycles/{ciclo_id}/overview",
    response_model=Dict[str, Any],
    summary="Dashboard general del ciclo",
    description=(
            "Retorna vista completa del ciclo:\n\n"
            "**KPIs:**\n"
            "- Días de ciclo\n"
            "- Biomasa total estimada (kg)\n"
            "- Densidad promedio ponderada (org/m²)\n"
            "- 4 estados (activos, en siembra, en cosecha, finalizados)\n"
            "- SOB operativo promedio (%)\n"
            "- PP promedio ponderado (g)\n\n"
            "**Gráficas:**\n"
            "- Curva de crecimiento (PP real vs proyectado por semana)\n"
            "- Evolución de biomasa acumulada\n"
            "- Evolución de densidad promedio\n\n"
            "**Operaciones próximas (7 días):**\n"
            "- Siembras pendientes\n"
            "- Cosechas planificadas"
    )
)
def get_cycle_dashboard(
        ciclo_id: int = Path(..., gt=0, description="ID del ciclo"),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Dashboard general del ciclo (vista Imagen 1).
    """
    return get_cycle_overview(
        db=db,
        user_id=user.usuario_id,
        is_admin=user.is_admin_global,
        ciclo_id=ciclo_id
    )


# ==========================================
# GET - Detalle Individual de Estanque
# ==========================================

@router.get(
    "/ponds/{estanque_id}/detail",
    response_model=Dict[str, Any],
    summary="Dashboard detallado de estanque",
    description=(
            "Retorna vista completa de un estanque en un ciclo:\n\n"
            "**KPIs:**\n"
            "- Biomasa estimada (kg)\n"
            "- Densidad actual (org/m²)\n"
            "- Organismos vivos totales\n"
            "- Peso promedio (g)\n"
            "- Supervivencia (%)\n\n"
            "**Gráficas:**\n"
            "- Curva de crecimiento del estanque (PP por semana)\n"
            "- Evolución de densidad (decrece por cosechas)\n\n"
            "**Detalles operativos:**\n"
            "- Estado, superficie, densidad inicial\n"
            "- Días de cultivo\n"
            "- Tasa de crecimiento (g/semana)\n"
            "- Biomasa por m²\n"
            "- Proyección de cosecha"
    )
)
def get_pond_dashboard(
        estanque_id: int = Path(..., gt=0, description="ID del estanque"),
        ciclo_id: int = Query(..., gt=0, description="ID del ciclo"),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Dashboard detallado de estanque (vista Imagen 2).
    """
    return get_pond_detail(
        db=db,
        user_id=user.usuario_id,
        is_admin=user.is_admin_global,
        estanque_id=estanque_id,
        ciclo_id=ciclo_id
    )


# ==========================================
# GET - Comparativa de Ciclos (PLACEHOLDER)
# ==========================================

@router.get(
    "/cycles/{ciclo_id}/compare",
    response_model=Dict[str, Any],
    summary="Comparar ciclo con históricos",
    description="Compara métricas del ciclo actual vs ciclos anteriores de la granja (PRÓXIMAMENTE)",
    deprecated=False,
    tags=["Analytics", "🚧 En Desarrollo"]
)
def compare_cycles(
        ciclo_id: int = Path(..., gt=0),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    TODO: Implementar comparativas históricas.

    Retornará:
    - Ciclo actual vs promedio histórico
    - Percentil de desempeño
    - Tendencias por granja
    """
    from fastapi import HTTPException
    raise HTTPException(
        status_code=501,
        detail="Endpoint en desarrollo. Disponible próximamente."
    )


# ==========================================
# GET - Proyección de Cosecha (PLACEHOLDER)
# ==========================================

@router.get(
    "/cycles/{ciclo_id}/harvest-projection",
    response_model=Dict[str, Any],
    summary="Proyección de cosecha del ciclo",
    description="Estima biomasa final y fecha óptima de cosecha (PRÓXIMAMENTE)",
    deprecated=False,
    tags=["Analytics", "🚧 En Desarrollo"]
)
def get_harvest_projection(
        ciclo_id: int = Path(..., gt=0),
        target_weight_g: float = Query(None, gt=0, description="Peso objetivo (g) - opcional"),
        db: Session = Depends(get_db),
        user: Usuario = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    TODO: Implementar proyección de cosecha.

    Retornará:
    - Biomasa estimada en fecha objetivo
    - Días restantes para peso objetivo
    - Ventana óptima de cosecha
    """
    from fastapi import HTTPException
    raise HTTPException(
        status_code=501,
        detail="Endpoint en desarrollo. Disponible próximamente."
    )