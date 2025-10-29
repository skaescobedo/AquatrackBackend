# services/reforecast_service.py
"""
Servicio de Reforecast Automático - Actualiza proyecciones con datos reales.

Triggers:
- Biometrías (anclaje de PP/SOB real)
- Siembras confirmadas/reprogramadas (shift de timeline)
- Cosechas confirmadas/reprogramadas (ajuste de retiros y SOB)
"""

from __future__ import annotations
from datetime import date, timedelta, datetime, time
from typing import Optional, List, Tuple, Dict, Any
from decimal import Decimal

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
    """Encuentra índices de líneas con anclajes. Siempre incluye primera y última línea."""
    indexes = set()

    for i, ln in enumerate(lines):
        if ln.nota and tag_prefix in ln.nota:
            indexes.add(i)

    # Siempre anclar inicio y fin
    if lines:
        indexes.add(0)
        indexes.add(len(lines) - 1)

    return sorted(list(indexes))


def _interpolate_series(values: List[float], anchors: List[int], shape: str) -> None:
    """Interpola serie completa entre anclajes (modifica in-place)"""
    if not values or len(values) <= 2:
        return

    anchors = sorted(set(anchors))

    if 0 not in anchors:
        anchors.insert(0, 0)
    if (len(values) - 1) not in anchors:
        anchors.append(len(values) - 1)

    for i in range(len(anchors) - 1):
        _interpolate_segment(values, anchors[i], anchors[i + 1], shape)


def _force_last_value_and_interpolate(
        values: List[float],
        anchors: List[int],
        target_last_value: float,
        shape: str = "s_curve"
) -> None:
    """
    Interpola serie FORZANDO el último valor a un objetivo específico.

    Args:
        values: Lista de valores a modificar (in-place)
        anchors: Índices de anclajes intermedios
        target_last_value: Valor objetivo para la última posición
        shape: Tipo de curva de interpolación
    """
    if not values:
        return

    last_idx = len(values) - 1
    values[last_idx] = target_last_value

    anchors_set = set(anchors)
    anchors_set.add(0)
    anchors_set.add(last_idx)

    sorted_anchors = sorted(list(anchors_set))

    for i in range(len(sorted_anchors) - 1):
        _interpolate_segment(values, sorted_anchors[i], sorted_anchors[i + 1], shape)


def _recalc_increments(values: List[float]) -> List[float]:
    """Recalcula incrementos semanales desde serie de PP"""
    increments = []
    for i, val in enumerate(values):
        if i == 0:
            increments.append(round(val, 3))
        else:
            increments.append(round(val - values[i - 1], 3))
    return increments


def _nearest_week_index(lines: List[ProyeccionLinea], when: date) -> int:
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
            detail=f"Ya existe un borrador manual (versión '{other_draft.version}'). Publícalo o cancélalo antes."
        )

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


# ===================================
# AGREGACIÓN PONDERADA: Cálculo
# ===================================

def calc_farm_weighted_pp_sob(
        db: Session,
        ciclo_id: int,
        fecha_inicio: date,
        fecha_fin: date
) -> Dict[str, Any]:
    """
    Calcula PP y SOB ponderados por población de la granja.

    Returns:
        {
            pp: float | None,
            sob: float | None,
            coverage_pct: float,
            measured_ponds: int,
            total_ponds: int
        }
    """
    ponds = _get_ponds_in_cycle(db, ciclo_id)
    total_ponds = len(ponds)

    if total_ponds == 0:
        return {
            "pp": None,
            "sob": None,
            "coverage_pct": 0.0,
            "measured_ponds": 0,
            "total_ponds": 0
        }

    plan = _get_siembra_plan(db, ciclo_id)
    dt_inicio, dt_fin = _date_range_to_datetime(fecha_inicio, fecha_fin)

    pp_weighted_sum = Decimal("0")
    pp_weight_sum = Decimal("0")
    sob_weighted_sum = Decimal("0")
    sob_weight_sum = Decimal("0")
    measured_ponds = 0

    for pond in ponds:
        siembra = (
            db.query(SiembraEstanque)
            .join(SiembraPlan)
            .filter(
                SiembraPlan.ciclo_id == ciclo_id,
                SiembraEstanque.estanque_id == pond.estanque_id,
                SiembraEstanque.status == 'f'
            )
            .first()
        )

        if not siembra:
            continue

        bio = (
            db.query(Biometria)
            .filter(
                Biometria.ciclo_id == ciclo_id,
                Biometria.estanque_id == pond.estanque_id,
                Biometria.fecha >= dt_inicio,
                Biometria.fecha <= dt_fin
            )
            .order_by(desc(Biometria.created_at))
            .first()
        )

        if not bio:
            continue

        measured_ponds += 1

        dens_base = _get_densidad_base(db, plan, pond.estanque_id)
        if dens_base is None or pond.superficie_m2 is None:
            continue

        retiros = _get_retiros_acumulados(db, ciclo_id, pond.estanque_id)
        dens_restante = dens_base - retiros
        if dens_restante < Decimal("0"):
            dens_restante = Decimal("0")

        area = Decimal(str(pond.superficie_m2))
        peso_base = dens_restante * area

        # Ponderar SOB
        if bio.sob_usada_pct is not None:
            sob_val = Decimal(str(bio.sob_usada_pct))
            sob_weighted_sum += sob_val * peso_base
            sob_weight_sum += peso_base

        # Ponderar PP
        if bio.pp_g is not None and bio.sob_usada_pct is not None:
            org_estimados = peso_base * (Decimal(str(bio.sob_usada_pct)) / Decimal("100"))
            pp_weighted_sum += Decimal(str(bio.pp_g)) * org_estimados
            pp_weight_sum += org_estimados

    pp_avg = float(pp_weighted_sum / pp_weight_sum) if pp_weight_sum > 0 else None
    sob_avg = float(sob_weighted_sum / sob_weight_sum) if sob_weight_sum > 0 else None
    coverage = (measured_ponds / total_ponds * 100.0) if total_ponds > 0 else 0.0

    return {
        "pp": round(pp_avg, 3) if pp_avg else None,
        "sob": round(sob_avg, 2) if sob_avg else None,
        "coverage_pct": round(coverage, 2),
        "measured_ponds": measured_ponds,
        "total_ponds": total_ponds
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

    Flujo:
    1. Obtener/crear borrador de reforecast
    2. Definir ventana de agregación (weekend o ±N días)
    3. Calcular PP y SOB ponderados de granja
    4. Validar umbrales (estanques mínimos, cobertura)
    5. Anclar valores reales en semana más cercana
    6. Recalcular SOB final objetivo
    7. Interpolar series FORZANDO el nuevo SOB final
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

    if settings.REFORECAST_WEEKEND_MODE:
        fecha_inicio, fecha_fin, anchor_date = _get_weekend_window(fecha_bio)
    else:
        radius = timedelta(days=settings.REFORECAST_WINDOW_DAYS)
        fecha_inicio = fecha_bio - radius
        fecha_fin = fecha_bio + radius
        anchor_date = fecha_bio

    agg = calc_farm_weighted_pp_sob(db, ciclo_id, fecha_inicio, fecha_fin)

    if agg["total_ponds"] == 0:
        return {"skipped": True, "reason": "no_ponds", "agg": agg}

    if agg["measured_ponds"] < settings.REFORECAST_MIN_PONDS:
        return {"skipped": True, "reason": "below_min_ponds", "agg": agg}

    if agg["coverage_pct"] < settings.REFORECAST_MIN_COVERAGE_PCT:
        return {"skipped": True, "reason": "below_coverage_threshold", "agg": agg}

    if agg["pp"] is None and agg["sob"] is None:
        return {"skipped": True, "reason": "no_aggregated_values", "agg": agg}

    lines: List[ProyeccionLinea] = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    if not lines:
        return {"skipped": True, "reason": "no_lines_in_draft"}

    week_idx = _nearest_week_index(lines, anchor_date)
    target_line = lines[week_idx]

    note_parts = []
    if target_line.nota:
        existing_tags = [
            tag.strip()
            for tag in target_line.nota.split("|")
            if "obs_pp:" not in tag and "obs_sob:" not in tag
        ]
        note_parts.extend(existing_tags)

    if agg["pp"] is not None:
        target_line.pp_g = round(float(agg["pp"]), 3)
        note_parts.append("obs_pp:bio_agg")

    if agg["sob"] is not None:
        sob_val = max(0.0, min(100.0, float(agg["sob"])))
        target_line.sob_pct_linea = round(sob_val, 2)
        note_parts.append("obs_sob:bio_agg")

    target_line.nota = " | ".join(note_parts) if note_parts else None

    pp_series = [float(ln.pp_g) for ln in lines]
    sob_series = [float(ln.sob_pct_linea) for ln in lines]

    pp_anchors = _anchor_indexes(lines, "obs_pp:")
    sob_anchors = _anchor_indexes(lines, "obs_sob:")

    # 🔧 PRIMERO: Recalcular SOB final objetivo
    nuevo_sob_final = None
    sob_final_anterior = draft.sob_final_objetivo_pct

    if agg["sob"] is not None:
        nuevo_sob_final = calc_sob_final_objetivo(db, ciclo_id, draft)
        draft.sob_final_objetivo_pct = nuevo_sob_final

        # Log único del cambio
        print(f"SOB Final Objetivo: {sob_final_anterior:.2f}% → {nuevo_sob_final:.2f}%")

    # 🔧 SEGUNDO: Interpolar series
    _interpolate_series(pp_series, pp_anchors, shape="s_curve")

    if nuevo_sob_final is not None:
        _force_last_value_and_interpolate(
            sob_series,
            sob_anchors,
            target_last_value=nuevo_sob_final,
            shape="s_curve"
        )
    else:
        _interpolate_series(sob_series, sob_anchors, shape="linear")

    for i, ln in enumerate(lines):
        ln.pp_g = round(pp_series[i], 3)
        ln.sob_pct_linea = round(max(0.0, min(100.0, sob_series[i])), 2)
        db.add(ln)

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
        "lines_updated": len(lines),
        "sob_final_objetivo_pct": draft.sob_final_objetivo_pct
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