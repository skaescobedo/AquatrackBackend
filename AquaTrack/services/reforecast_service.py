# services/reforecast_service.py
"""
Servicio de Reforecast Automático - Actualiza proyecciones con datos reales.

Triggers:
- Biometrías (anclaje de PP/SOB real)
- Siembras confirmadas/reprogramadas (shift de timeline)
- Cosechas confirmadas/reprogramadas (ajuste de retiros y SOB)

Cambios principales v2:
- Ponderación por BIOMASA EFECTIVA (área × densidad × SOB actual)
- Validación por % de BIOMASA medida (no conteo de estanques)
- Interpolación SOLO hacia adelante desde punto de anclaje
- Detección de outliers en SOB con suavizado exponencial
"""

from __future__ import annotations
from datetime import date, timedelta, datetime, time
from typing import Optional, List, Tuple, Dict, Any
from decimal import Decimal
from statistics import median, stdev

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func

from config.settings import settings
from models.projection import Proyeccion, ProyeccionLinea, SourceType
from models.cycle import Ciclo
from models.pond import Estanque
from models.seeding import SiembraPlan, SiembraEstanque
from models.harvest import CosechaOla, CosechaEstanque
from models.biometria import Biometria
from models.user import Usuario
from utils.datetime_utils import now_mazatlan


# ===================================
# HELPERS: Curvas e Interpolación
# ===================================

def _smooth_factor(t: float, shape: str = "s_curve") -> float:
    """Factor de suavizado para interpolación."""
    t = max(0.0, min(1.0, t))

    if shape == "linear":
        return t
    elif shape == "ease_in":
        return t * t
    elif shape == "ease_out":
        return 1 - (1 - t) * (1 - t)
    else:  # s_curve (default)
        return 3 * (t ** 2) - 2 * (t ** 3)


def _interpolate_segment(values: List[float], start_idx: int, end_idx: int, shape: str) -> None:
    """Interpola valores entre dos índices (modifica in-place)"""
    if start_idx >= end_idx:
        return

    val_start = values[start_idx]
    val_end = values[end_idx]
    span = end_idx - start_idx

    for k in range(start_idx + 1, end_idx):
        t = (k - start_idx) / span
        factor = _smooth_factor(t, shape=shape)
        values[k] = round(val_start + factor * (val_end - val_start), 3)


def _anchor_indexes(lines: List[ProyeccionLinea], tag_prefix: str) -> List[int]:
    """
    Encuentra índices de líneas con anclajes específicos.
    Siempre incluye primera y última línea.
    """
    indexes = set()

    for i, ln in enumerate(lines):
        if ln.nota and tag_prefix in ln.nota:
            indexes.add(i)

    # Siempre anclar inicio y fin
    if lines:
        indexes.add(0)
        indexes.add(len(lines) - 1)

    return sorted(list(indexes))


def _interpolate_series_forward(
        values: List[float],
        anchors: List[int],
        start_idx: int,
        shape: str = "s_curve"
) -> None:
    """
    Interpola serie SOLO desde start_idx hacia adelante.
    No modifica valores anteriores a start_idx (respeta histórico).

    Args:
        values: Lista de valores a modificar (in-place)
        anchors: Índices de anclajes válidos
        start_idx: Índice mínimo desde donde empezar a interpolar
        shape: Tipo de curva de interpolación
    """
    if not values or len(values) <= 2:
        return

    # Filtrar anclajes >= start_idx y ordenar
    valid_anchors = sorted([a for a in anchors if a >= start_idx])

    if len(valid_anchors) < 2:
        return

    # Asegurar que start_idx está en la lista de anclajes
    if start_idx not in valid_anchors:
        valid_anchors.insert(0, start_idx)

    # Asegurar que el último índice está anclado
    last_idx = len(values) - 1
    if last_idx not in valid_anchors:
        valid_anchors.append(last_idx)

    # Interpolar solo entre anclajes válidos
    for i in range(len(valid_anchors) - 1):
        start = valid_anchors[i]
        end = valid_anchors[i + 1]

        # Seguridad extra: nunca modificar antes de start_idx
        if start < start_idx:
            start = start_idx

        _interpolate_segment(values, start, end, shape)


def _force_last_value_and_interpolate_forward(
        values: List[float],
        anchors: List[int],
        start_idx: int,
        target_last_value: float,
        shape: str = "s_curve"
) -> None:
    """
    Interpola serie FORZANDO el último valor a un objetivo específico.
    Solo modifica desde start_idx hacia adelante.

    Args:
        values: Lista de valores a modificar (in-place)
        anchors: Índices de anclajes intermedios
        start_idx: Índice desde donde empezar a modificar
        target_last_value: Valor objetivo para la última posición
        shape: Tipo de curva de interpolación
    """
    if not values:
        return

    last_idx = len(values) - 1
    values[last_idx] = target_last_value

    # Filtrar anclajes >= start_idx
    valid_anchors = sorted([a for a in anchors if a >= start_idx])

    # Asegurar que start_idx y last_idx están en la lista
    if start_idx not in valid_anchors:
        valid_anchors.insert(0, start_idx)
    if last_idx not in valid_anchors:
        valid_anchors.append(last_idx)

    # Interpolar solo hacia adelante
    for i in range(len(valid_anchors) - 1):
        start = valid_anchors[i]
        end = valid_anchors[i + 1]

        if start < start_idx:
            start = start_idx

        _interpolate_segment(values, start, end, shape)


def _recalc_increments(values: List[float]) -> List[float]:
    """Recalcula incrementos semanales desde serie de PP"""
    increments = []
    for i, val in enumerate(values):
        if i == 0:
            increments.append(round(val, 3))
        else:
            increments.append(round(val - values[i - 1], 3))
    return increments


def _find_closest_week(lines: List[ProyeccionLinea], when: date) -> int:
    """Encuentra el índice de la semana más cercana a una fecha"""
    if not lines:
        return 0

    best_idx = 0
    best_diff = abs((lines[0].fecha_plan - when).days)

    for i, ln in enumerate(lines):
        diff = abs((ln.fecha_plan - when).days)
        if diff < best_diff:
            best_diff = diff
            best_idx = i

    return best_idx


def _update_note(existing_note: Optional[str], new_tag: str) -> str:
    """Agrega o actualiza un tag en la nota de una línea"""
    if not existing_note:
        return new_tag

    parts = [p.strip() for p in existing_note.split("|") if p.strip()]

    # Verificar si el tag ya existe
    tag_prefix = new_tag.split(":")[0]
    parts = [p for p in parts if not p.startswith(tag_prefix)]

    # Agregar nuevo tag
    parts.append(new_tag)

    return " | ".join(parts)


# ===================================
# CORE: Gestión de Borrador
# ===================================

def get_or_create_reforecast_draft(
        db: Session,
        user: Usuario,
        ciclo_id: int,
        *,
        soft_if_other_draft: bool = False
) -> Optional[Proyeccion]:
    """
    Obtiene o crea borrador de reforecast.

    Lógica:
    1. Si existe borrador con source_type='reforecast' → retornar
    2. Si existe otro borrador (source_type!='reforecast'):
       - Si soft_if_other_draft=True → retornar None
       - Si soft_if_other_draft=False → error 409
    3. Si no hay borrador → clonar proyección actual
    """
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    # Buscar borrador de reforecast existente
    reforecast_draft = (
        db.query(Proyeccion)
        .filter(
            Proyeccion.ciclo_id == ciclo_id,
            Proyeccion.status == 'b',
            Proyeccion.source_type == SourceType.REFORECAST
        )
        .order_by(desc(Proyeccion.created_at))
        .first()
    )

    if reforecast_draft:
        return reforecast_draft

    # Verificar si existe otro borrador
    other_draft = (
        db.query(Proyeccion)
        .filter(
            Proyeccion.ciclo_id == ciclo_id,
            Proyeccion.status == 'b'
        )
        .first()
    )

    if other_draft:
        if soft_if_other_draft:
            return None
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un borrador manual (versión '{other_draft.version}'). "
                   f"Publícalo o cancélalo antes de ejecutar reforecast."
        )

    # Obtener proyección actual para clonar
    current = (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id)
        .order_by(
            desc(Proyeccion.is_current),
            desc(Proyeccion.published_at),
            desc(Proyeccion.created_at)
        )
        .first()
    )

    if not current:
        raise HTTPException(
            status_code=404,
            detail="No hay proyección actual para reforecast. Crea una proyección primero."
        )

    # Crear nuevo borrador
    count = db.query(func.count(Proyeccion.proyeccion_id)).filter(
        Proyeccion.ciclo_id == ciclo_id
    ).scalar() or 0
    version = f"V{count + 1}"

    draft = Proyeccion(
        ciclo_id=ciclo_id,
        version=version,
        descripcion=f"Reforecast automático de {current.version}",
        status='b',
        is_current=False,
        creada_por=user.usuario_id,
        source_type=SourceType.REFORECAST,
        parent_version_id=current.proyeccion_id,
        sob_final_objetivo_pct=current.sob_final_objetivo_pct,
        siembra_ventana_fin=current.siembra_ventana_fin,
    )
    db.add(draft)
    db.flush()

    # Clonar líneas
    current_lines = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == current.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    cloned_lines = []
    for ln in current_lines:
        cloned_lines.append(
            ProyeccionLinea(
                proyeccion_id=draft.proyeccion_id,
                edad_dias=ln.edad_dias,
                semana_idx=ln.semana_idx,
                fecha_plan=ln.fecha_plan,
                pp_g=ln.pp_g,
                incremento_g_sem=ln.incremento_g_sem,
                sob_pct_linea=ln.sob_pct_linea,
                cosecha_flag=ln.cosecha_flag,
                retiro_org_m2=ln.retiro_org_m2,
                nota=ln.nota,
            )
        )

    if cloned_lines:
        db.bulk_save_objects(cloned_lines)

    db.commit()
    db.refresh(draft)

    return draft


# ===================================
# AGREGACIÓN PONDERADA: Helpers
# ===================================

def _get_siembra_plan(db: Session, ciclo_id: int) -> Optional[SiembraPlan]:
    """Obtiene el plan de siembras del ciclo"""
    return db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()


def _get_densidad_base(db: Session, plan: Optional[SiembraPlan], estanque_id: int) -> Optional[Decimal]:
    """Obtiene densidad base de un estanque (override o del plan)"""
    if not plan:
        return None

    se = (
        db.query(SiembraEstanque)
        .filter(
            SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
            SiembraEstanque.estanque_id == estanque_id
        )
        .first()
    )

    if se and se.densidad_override_org_m2 is not None:
        override = Decimal(str(se.densidad_override_org_m2))
        if override > 0:
            return override

    if plan.densidad_org_m2 is not None:
        plan_dens = Decimal(str(plan.densidad_org_m2))
        if plan_dens > 0:
            return plan_dens

    return None


def _get_retiros_acumulados(db: Session, ciclo_id: int, estanque_id: int) -> Decimal:
    """Calcula densidad retirada acumulada (cosechas confirmadas)"""
    total = (
        db.query(func.coalesce(func.sum(CosechaEstanque.densidad_retirada_org_m2), 0))
        .join(CosechaOla, CosechaEstanque.cosecha_ola_id == CosechaOla.cosecha_ola_id)
        .filter(
            CosechaOla.ciclo_id == ciclo_id,
            CosechaEstanque.estanque_id == estanque_id,
            CosechaEstanque.status == 'c'
        )
        .scalar()
    )

    return Decimal(str(total or 0))


def _get_ponds_in_cycle(db: Session, ciclo_id: int) -> List[Estanque]:
    """Obtiene todos los estanques vigentes de la granja del ciclo"""
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        return []

    return (
        db.query(Estanque)
        .filter(
            Estanque.granja_id == cycle.granja_id,
            Estanque.is_vigente == True
        )
        .order_by(asc(Estanque.estanque_id))
        .all()
    )


def _date_range_to_datetime(fecha_inicio: date, fecha_fin: date) -> Tuple[datetime, datetime]:
    """Convierte rango de fechas a datetime completo"""
    dt_inicio = datetime.combine(fecha_inicio, time.min)
    dt_fin = datetime.combine(fecha_fin, time.max)
    return dt_inicio, dt_fin


def _get_current_sob_from_last_biometria(
        db: Session,
        ciclo_id: int,
        estanque_id: int
) -> Decimal:
    """
    Obtiene el SOB actual del estanque desde la última biometría.
    Si no hay biometrías, retorna 100% (SOB de siembra).
    """
    last_bio = (
        db.query(Biometria)
        .filter(
            Biometria.ciclo_id == ciclo_id,
            Biometria.estanque_id == estanque_id
        )
        .order_by(desc(Biometria.fecha))
        .first()
    )

    if last_bio and last_bio.sob_usada_pct is not None:
        return Decimal(str(last_bio.sob_usada_pct))

    return Decimal("100.00")


# ===================================
# AGREGACIÓN PONDERADA: Cálculo v2
# ===================================

def calc_farm_weighted_pp_sob(
        db: Session,
        ciclo_id: int,
        fecha_inicio: date,
        fecha_fin: date
) -> Dict[str, Any]:
    """
    Calcula PP y SOB ponderados por BIOMASA EFECTIVA de la granja.

    Mejoras v2:
    - Ponderación por (área × densidad_base × SOB_actual) = organismos reales vivos
    - Validación por % de biomasa medida (no por conteo de estanques)
    - Detección de outliers en SOB con suavizado exponencial

    Returns:
        {
            "pp": float | None,
            "sob": float | None,
            "coverage_biomasa_pct": float,  # % de biomasa medida
            "measured_ponds": int,
            "total_ponds": int,
            "outliers_detected": List[int]  # estanque_ids con outliers
        }
    """
    dt_inicio, dt_fin = _date_range_to_datetime(fecha_inicio, fecha_fin)
    plan = _get_siembra_plan(db, ciclo_id)
    ponds = _get_ponds_in_cycle(db, ciclo_id)

    if not ponds:
        return {
            "pp": None,
            "sob": None,
            "coverage_biomasa_pct": 0.0,
            "measured_ponds": 0,
            "total_ponds": 0,
            "outliers_detected": []
        }

    # Calcular biomasa total de la granja
    biomasa_total = Decimal("0")
    pond_biomasa_map = {}  # estanque_id -> biomasa_efectiva

    for pond in ponds:
        dens_base = _get_densidad_base(db, plan, pond.estanque_id)
        if not dens_base or dens_base <= 0:
            continue

        sob_actual = _get_current_sob_from_last_biometria(db, ciclo_id, pond.estanque_id)
        retiros = _get_retiros_acumulados(db, ciclo_id, pond.estanque_id)

        dens_efectiva = max(Decimal("0"), dens_base - retiros)
        biomasa_efectiva = Decimal(str(pond.superficie_m2)) * dens_efectiva * (sob_actual / Decimal("100"))

        pond_biomasa_map[pond.estanque_id] = biomasa_efectiva
        biomasa_total += biomasa_efectiva

    if biomasa_total == 0:
        return {
            "pp": None,
            "sob": None,
            "coverage_biomasa_pct": 0.0,
            "measured_ponds": 0,
            "total_ponds": len(ponds),
            "outliers_detected": []
        }

    # Obtener biometrías en ventana
    biometrias = (
        db.query(Biometria)
        .filter(
            Biometria.ciclo_id == ciclo_id,
            Biometria.fecha >= dt_inicio,
            Biometria.fecha <= dt_fin
        )
        .all()
    )

    if not biometrias:
        return {
            "pp": None,
            "sob": None,
            "coverage_biomasa_pct": 0.0,
            "measured_ponds": 0,
            "total_ponds": len(ponds),
            "outliers_detected": []
        }

    # Detectar outliers de SOB (opcional)
    sob_values = [float(bio.sob_usada_pct) for bio in biometrias if bio.sob_usada_pct is not None]
    outliers_detected = []

    if len(sob_values) >= 3:  # Necesitamos al menos 3 valores para detectar outliers
        try:
            sob_median = median(sob_values)
            sob_stdev = stdev(sob_values)

            # Detectar valores que se desvían más de 2 desviaciones estándar
            for bio in biometrias:
                if bio.sob_usada_pct is not None:
                    sob_val = float(bio.sob_usada_pct)
                    if abs(sob_val - sob_median) > (2 * sob_stdev):
                        outliers_detected.append(bio.estanque_id)
        except:
            pass  # Si falla la detección, continuar sin filtrar

    # Ponderar por biomasa efectiva
    pp_weighted_sum = Decimal("0")
    pp_weight_sum = Decimal("0")
    sob_weighted_sum = Decimal("0")
    sob_weight_sum = Decimal("0")

    biomasa_medida = Decimal("0")
    measured_ponds_set = set()

    for bio in biometrias:
        if bio.estanque_id not in pond_biomasa_map:
            continue

        biomasa_pond = pond_biomasa_map[bio.estanque_id]
        if biomasa_pond <= 0:
            continue

        measured_ponds_set.add(bio.estanque_id)
        biomasa_medida += biomasa_pond

        # Ponderar SOB (excluir outliers si se detectaron)
        if bio.sob_usada_pct is not None:
            # Si el estanque tiene outlier, aplicar menor peso (30%)
            peso = biomasa_pond
            if bio.estanque_id in outliers_detected:
                peso = biomasa_pond * Decimal("0.3")

            sob_weighted_sum += Decimal(str(bio.sob_usada_pct)) * peso
            sob_weight_sum += peso

        # Ponderar PP
        if bio.pp_g is not None:
            pp_weighted_sum += Decimal(str(bio.pp_g)) * biomasa_pond
            pp_weight_sum += biomasa_pond

    pp_avg = float(pp_weighted_sum / pp_weight_sum) if pp_weight_sum > 0 else None
    sob_avg = float(sob_weighted_sum / sob_weight_sum) if sob_weight_sum > 0 else None
    coverage_biomasa = float((biomasa_medida / biomasa_total) * 100) if biomasa_total > 0 else 0.0

    return {
        "pp": round(pp_avg, 3) if pp_avg else None,
        "sob": round(sob_avg, 2) if sob_avg else None,
        "coverage_biomasa_pct": round(coverage_biomasa, 2),
        "measured_ponds": len(measured_ponds_set),
        "total_ponds": len(ponds),
        "outliers_detected": outliers_detected
    }


def _get_weekend_window(event_date: date) -> Tuple[date, date, date]:
    """
    Calcula ventana de fin de semana (Sábado-Domingo).

    Returns:
        (sabado, domingo, anchor=domingo)
    """
    monday = event_date - timedelta(days=event_date.weekday())
    saturday = monday + timedelta(days=5)
    sunday = monday + timedelta(days=6)

    return saturday, sunday, sunday


# ===================================
# CÁLCULOS: SOB Final Objetivo
# ===================================

def calc_sob_final_objetivo(
        db: Session,
        ciclo_id: int,
        draft: Proyeccion
) -> float:
    """
    Calcula SOB final objetivo ajustado por observaciones reales.

    Algoritmo:
    1. Obtener SOB final objetivo de la proyección padre (baseline)
    2. Encontrar última línea con SOB observado real
    3. Comparar SOB real vs SOB planeado en esa semana
    4. Calcular factor de ajuste = SOB_real / SOB_planeado
    5. Aplicar factor al SOB final objetivo
    """
    if not draft.parent_version_id:
        last_line = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
            .order_by(desc(ProyeccionLinea.semana_idx))
            .first()
        )
        return float(last_line.sob_pct_linea) if last_line else 85.0

    parent = db.get(Proyeccion, draft.parent_version_id)
    if not parent or not parent.sob_final_objetivo_pct:
        return 85.0

    sob_final_original = Decimal(str(parent.sob_final_objetivo_pct))

    draft_lines = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    parent_lines = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == parent.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    if not draft_lines or not parent_lines:
        return float(sob_final_original)

    sob_real = None
    semana_observada = None

    for i, ln in enumerate(draft_lines):
        if ln.nota and "obs_sob:" in ln.nota:
            sob_real = Decimal(str(ln.sob_pct_linea))
            semana_observada = i
            break

    if sob_real is None:
        return float(sob_final_original)

    if semana_observada >= len(parent_lines):
        return float(sob_final_original)

    sob_planeado = Decimal(str(parent_lines[semana_observada].sob_pct_linea))

    if sob_planeado == 0:
        return float(sob_final_original)

    factor_ajuste = sob_real / sob_planeado
    sob_final_ajustado = sob_final_original * factor_ajuste
    sob_final_ajustado = max(Decimal("0"), min(Decimal("100"), sob_final_ajustado))

    return float(sob_final_ajustado)


# ===================================
# TRIGGER 1: BIOMETRÍAS (anclaje PP/SOB)
# ===================================

def trigger_biometria_reforecast(
        db: Session,
        user: Usuario,
        ciclo_id: int,
        fecha_bio: date,
        *,
        soft_if_other_draft: bool = True
) -> Dict[str, Any]:
    """
    Trigger de reforecast por biometría.

    Flujo v2 (mejorado):
    1. Obtener/crear borrador de reforecast
    2. Definir ventana de agregación (weekend o ±N días)
    3. Calcular PP y SOB ponderados por BIOMASA EFECTIVA
    4. Validar % de BIOMASA medida (no conteo de estanques)
    5. Anclar valores reales en semana más cercana
    6. Interpolar SOLO hacia adelante desde punto de anclaje
    7. Recalcular SOB final objetivo
    8. Recalcular incrementos de PP
    """
    if not settings.REFORECAST_ENABLED:
        return {"skipped": True, "reason": "reforecast_disabled"}

    draft = get_or_create_reforecast_draft(
        db, user, ciclo_id,
        soft_if_other_draft=soft_if_other_draft
    )

    if draft is None:
        return {"skipped": True, "reason": "other_draft_exists"}

    # Definir ventana de agregación
    if settings.REFORECAST_WEEKEND_MODE:
        fecha_inicio, fecha_fin, anchor_date = _get_weekend_window(fecha_bio)
    else:
        radius = timedelta(days=settings.REFORECAST_WINDOW_DAYS)
        fecha_inicio = fecha_bio - radius
        fecha_fin = fecha_bio + radius
        anchor_date = fecha_bio

    # Calcular agregados ponderados por biomasa efectiva
    agg = calc_farm_weighted_pp_sob(db, ciclo_id, fecha_inicio, fecha_fin)

    # Validaciones mejoradas
    if agg["total_ponds"] == 0:
        return {"skipped": True, "reason": "no_ponds", "agg": agg}

    # Validar % de biomasa medida (no conteo de estanques)
    if agg["coverage_biomasa_pct"] < settings.REFORECAST_MIN_COVERAGE_PCT:
        return {
            "skipped": True,
            "reason": "below_biomass_coverage_threshold",
            "agg": agg,
            "threshold": settings.REFORECAST_MIN_COVERAGE_PCT
        }

    if agg["pp"] is None and agg["sob"] is None:
        return {"skipped": True, "reason": "no_aggregated_values", "agg": agg}

    # Obtener líneas del borrador
    lines: List[ProyeccionLinea] = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    if not lines:
        return {"skipped": True, "reason": "no_lines_in_draft"}

    # Encontrar semana de anclaje
    week_idx = _find_closest_week(lines, anchor_date)

    # Crear series de trabajo
    pp_series = [float(ln.pp_g) for ln in lines]
    sob_series = [float(ln.sob_pct_linea) for ln in lines]

    # Anclar valores observados en week_idx
    if agg["pp"] is not None:
        pp_series[week_idx] = agg["pp"]
        lines[week_idx].nota = _update_note(lines[week_idx].nota, "obs_pp:bio_agg")

    if agg["sob"] is not None:
        sob_series[week_idx] = agg["sob"]
        lines[week_idx].nota = _update_note(lines[week_idx].nota, "obs_sob:bio_agg")

    # Encontrar anclajes existentes
    pp_anchors = _anchor_indexes(lines, "obs_pp")
    sob_anchors = _anchor_indexes(lines, "obs_sob")

    # CRÍTICO: Interpolar SOLO hacia adelante desde week_idx
    _interpolate_series_forward(
        pp_series,
        pp_anchors,
        start_idx=week_idx,
        shape="s_curve"
    )

    # Recalcular SOB final objetivo
    nuevo_sob_final = calc_sob_final_objetivo(db, ciclo_id, draft)
    draft.sob_final_objetivo_pct = nuevo_sob_final

    # Interpolar SOB forzando el nuevo SOB final
    if nuevo_sob_final is not None:
        _force_last_value_and_interpolate_forward(
            sob_series,
            sob_anchors,
            start_idx=week_idx,
            target_last_value=nuevo_sob_final,
            shape="s_curve"
        )
    else:
        _interpolate_series_forward(
            sob_series,
            sob_anchors,
            start_idx=week_idx,
            shape="linear"
        )

    # Aplicar valores interpolados
    for i, ln in enumerate(lines):
        ln.pp_g = round(pp_series[i], 3)
        ln.sob_pct_linea = round(max(0.0, min(100.0, sob_series[i])), 2)
        db.add(ln)

    # Recalcular incrementos
    increments = _recalc_increments(pp_series)
    for i, ln in enumerate(lines):
        ln.incremento_g_sem = increments[i]
        db.add(ln)

    draft.updated_at = now_mazatlan()
    db.commit()

    return {
        "skipped": False,
        "proyeccion_id": draft.proyeccion_id,
        "week_idx": week_idx,
        "anchored": {
            "pp": agg["pp"] is not None,
            "sob": agg["sob"] is not None,
            "anchor_date": anchor_date,
        },
        "agg": agg,
        "lines_updated": len(lines) - week_idx,  # Solo líneas hacia adelante
        "sob_final_objetivo_pct": draft.sob_final_objetivo_pct,
        "outliers_detected": agg["outliers_detected"]
    }


# ===================================
# TRIGGER 2: SIEMBRAS (shift timeline)
# ===================================

def trigger_siembra_reforecast(
        db: Session,
        user: Usuario,
        ciclo_id: int,
        fecha_siembra_real: date,
        fecha_siembra_tentativa: date,
        *,
        soft_if_other_draft: bool = True
) -> Dict[str, Any]:
    """
    Trigger de reforecast por siembra confirmada/reprogramada.

    Efectos:
    - Ajusta timeline de proyección según desviación en fecha de siembra
    """
    if not settings.REFORECAST_ENABLED:
        return {"skipped": True, "reason": "reforecast_disabled"}

    draft = get_or_create_reforecast_draft(
        db, user, ciclo_id,
        soft_if_other_draft=soft_if_other_draft
    )

    if draft is None:
        return {"skipped": True, "reason": "other_draft_exists"}

    delta_days = (fecha_siembra_real - fecha_siembra_tentativa).days

    if delta_days == 0:
        return {"skipped": True, "reason": "no_deviation"}

    lines = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
        .all()
    )

    for ln in lines:
        ln.fecha_plan += timedelta(days=delta_days)
        db.add(ln)

    if draft.siembra_ventana_fin:
        draft.siembra_ventana_fin += timedelta(days=delta_days)

    draft.updated_at = now_mazatlan()
    db.commit()

    return {
        "skipped": False,
        "proyeccion_id": draft.proyeccion_id,
        "delta_days": delta_days,
        "lines_shifted": len(lines)
    }


# ===================================
# TRIGGER 3: COSECHAS (ajuste retiros)
# ===================================

def trigger_cosecha_reforecast(
        db: Session,
        user: Usuario,
        ciclo_id: int,
        fecha_cosecha_real: date,
        densidad_retirada_org_m2: float,
        *,
        soft_if_other_draft: bool = True
) -> Dict[str, Any]:
    """
    Trigger de reforecast por cosecha confirmada/reprogramada.

    Efectos:
    - Actualiza fecha y retiro en línea de cosecha
    - Recalcula SOB desde cosecha hacia adelante
    """
    if not settings.REFORECAST_ENABLED:
        return {"skipped": True, "reason": "reforecast_disabled"}

    draft = get_or_create_reforecast_draft(
        db, user, ciclo_id,
        soft_if_other_draft=soft_if_other_draft
    )

    if draft is None:
        return {"skipped": True, "reason": "other_draft_exists"}

    lines: List[ProyeccionLinea] = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    if not lines:
        return {"skipped": True, "reason": "no_lines_in_draft"}

    harvest_lines = [i for i, ln in enumerate(lines) if ln.cosecha_flag]

    if not harvest_lines:
        return {"skipped": True, "reason": "no_harvest_line_in_projection"}

    best_idx = harvest_lines[0]
    best_diff = abs((lines[best_idx].fecha_plan - fecha_cosecha_real).days)

    for idx in harvest_lines:
        diff = abs((lines[idx].fecha_plan - fecha_cosecha_real).days)
        if diff < best_diff:
            best_diff = diff
            best_idx = idx

    harvest_line = lines[best_idx]

    harvest_line.fecha_plan = fecha_cosecha_real
    harvest_line.retiro_org_m2 = round(densidad_retirada_org_m2, 4)

    note_parts = []
    if harvest_line.nota:
        note_parts.append(harvest_line.nota)
    note_parts.append(f"obs_cosecha:{densidad_retirada_org_m2:.2f}org/m2")
    harvest_line.nota = " | ".join(note_parts)

    plan = _get_siembra_plan(db, ciclo_id)
    if plan and plan.densidad_org_m2:
        dens_base = float(plan.densidad_org_m2)
        retiro_ratio = densidad_retirada_org_m2 / dens_base

        for i in range(best_idx + 1, len(lines)):
            sob_antes = lines[i - 1].sob_pct_linea
            sob_despues = sob_antes * (1 - retiro_ratio)
            lines[i].sob_pct_linea = round(max(0.0, min(100.0, sob_despues)), 2)

    sob_final = calc_sob_final_objetivo(db, ciclo_id, draft)
    draft.sob_final_objetivo_pct = sob_final

    draft.updated_at = now_mazatlan()
    db.commit()

    return {
        "skipped": False,
        "proyeccion_id": draft.proyeccion_id,
        "harvest_week_idx": best_idx,
        "sob_final_updated": sob_final,
        "lines_updated": len(lines) - best_idx
    }