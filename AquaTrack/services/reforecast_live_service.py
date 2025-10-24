# services/reforecast_live_service.py
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Tuple, Dict, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func, or_

from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from models.ciclo import Ciclo
from models.usuario import Usuario

# Para agregación ponderada
from models.estanque import Estanque
from models.siembra_plan import SiembraPlan
from models.siembra_estanque import SiembraEstanque
from models.plan_cosechas import PlanCosechas
from models.cosecha_ola import CosechaOla
from models.cosecha_estanque import CosechaEstanque
from models.biometria import Biometria

from services.permissions_service import ensure_user_in_farm_or_admin


# -------- Configuración por defecto --------
WINDOW_RADIUS_DAYS_DEFAULT = 1          # modo ventana libre: 3 días [d-1 .. d .. d+1]
COVERAGE_THRESHOLD_DEFAULT = 0.30       # 30%
MIN_PONDS_FOR_COVERAGE_DEFAULT = 1      # súbelo si quieres

# -------- helpers base (curvas/interpolación) --------

def _smooth_factor(t: float, shape: str = "s_curve") -> float:
    t = max(0.0, min(1.0, t))
    if shape == "linear":
        return t
    if shape == "ease_in":
        return t * t
    if shape == "ease_out":
        return 1 - (1 - t) * (1 - t)
    return 3 * (t ** 2) - 2 * (t ** 3)


def _nearest_week_index(lines: List[ProyeccionLinea], when: date) -> int:
    if not lines:
        return 0
    best_i = 0
    best_diff = abs((lines[0].fecha_plan - when).days)
    for i, ln in enumerate(lines):
        d = abs((ln.fecha_plan - when).days)
        if d < best_diff:
            best_diff = d
            best_i = i
    return best_i


def _anchor_indexes(lines: List[ProyeccionLinea], tag_prefix: str) -> List[int]:
    idxs = set()
    for i, l in enumerate(lines):
        if l.nota and tag_prefix in l.nota:
            idxs.add(i)
    if lines:
        idxs.add(0)
        idxs.add(len(lines) - 1)
    return sorted(list(idxs))


def _interpolate_segment(values: List[float], a: int, b: int, shape: str) -> None:
    if a >= b:
        return
    va, vb = values[a], values[b]
    span = b - a
    for k in range(a + 1, b):
        t = (k - a) / span
        f = _smooth_factor(t, shape=shape)
        values[k] = round(va + f * (vb - va), 3)


def _interpolate_series(values: List[float], anchors: List[int], shape: str) -> None:
    if not values or len(values) <= 2:
        return
    anchors = sorted(set(anchors))
    if 0 not in anchors:
        anchors.insert(0, 0)
    if (len(values) - 1) not in anchors:
        anchors.append(len(values) - 1)
    for i in range(len(anchors) - 1):
        _interpolate_segment(values, anchors[i], anchors[i + 1], shape=shape)


def _recalc_increments(values: List[float]) -> List[float]:
    inc = []
    for i, v in enumerate(values):
        if i == 0:
            inc.append(round(v, 3))
        else:
            inc.append(round(v - values[i - 1], 3))
    return inc


def _clone_from_current_projection(db: Session, user: Usuario, ciclo_id: int) -> Optional[Proyeccion]:
    cur = (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id)
        .order_by(
            desc(Proyeccion.is_current),
            Proyeccion.published_at.is_(None).asc(),
            desc(Proyeccion.published_at),
            desc(Proyeccion.created_at),
        )
        .first()
    )
    if not cur:
        return None

    cnt = db.query(func.count(Proyeccion.proyeccion_id)).filter(Proyeccion.ciclo_id == ciclo_id).scalar() or 0
    version = f"v{cnt + 1}"

    draft = Proyeccion(
        ciclo_id=ciclo_id,
        version=version,
        descripcion=f"Borrador reforecast de {cur.version}",
        status="b",
        is_current=False,
        creada_por=user.usuario_id,
        source_type="reforecast",
        parent_version_id=cur.proyeccion_id,
        sob_final_objetivo_pct=cur.sob_final_objetivo_pct,
        siembra_ventana_fin=cur.siembra_ventana_fin,
    )
    db.add(draft)
    db.flush()

    lines = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == cur.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx), asc(ProyeccionLinea.fecha_plan))
        .all()
    )
    clones = []
    for l in lines:
        clones.append(
            ProyeccionLinea(
                proyeccion_id=draft.proyeccion_id,
                edad_dias=l.edad_dias,
                semana_idx=l.semana_idx,
                fecha_plan=l.fecha_plan,
                pp_g=l.pp_g,
                incremento_g_sem=l.incremento_g_sem,
                sob_pct_linea=l.sob_pct_linea,
                cosecha_flag=l.cosecha_flag,
                retiro_org_m2=l.retiro_org_m2,
                nota=l.nota,
            )
        )
    if clones:
        db.bulk_save_objects(clones)
    db.commit()
    db.refresh(draft)
    return draft


# -------- API base (igual que antes) --------

def ensure_reforecast_draft(
    db: Session,
    user: Usuario,
    ciclo_id: int,
    *,
    soft_if_other_draft: bool = False,
) -> Optional[Proyeccion]:
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    re_draft = (
        db.query(Proyeccion)
        .filter(
            Proyeccion.ciclo_id == ciclo_id,
            Proyeccion.status == "b",
            Proyeccion.source_type == "reforecast",
        )
        .order_by(desc(Proyeccion.created_at))
        .first()
    )
    if re_draft:
        return re_draft

    other = (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id, Proyeccion.status == "b")
        .first()
    )
    if other:
        if soft_if_other_draft:
            return None
        raise HTTPException(status_code=409, detail="draft_projection_already_exists")

    return _clone_from_current_projection(db, user, ciclo_id)


def observe_and_rebuild(
    db: Session,
    user: Usuario,
    ciclo_id: int,
    *,
    event_date: date,
    set_pp: Optional[float],
    set_sob: Optional[float],
    reason: str = "obs",
    soft_if_other_draft: bool = False,
) -> dict:
    if set_pp is None and set_sob is None:
        raise HTTPException(status_code=422, detail="at_least_one_of_pp_or_sob_required")

    draft = ensure_reforecast_draft(db, user, ciclo_id, soft_if_other_draft=soft_if_other_draft)
    if draft is None:
        return {"skipped": True, "reason": "another_draft_exists"}

    lines: List[ProyeccionLinea] = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx), asc(ProyeccionLinea.fecha_plan))
        .all()
    )
    if not lines:
        return {"skipped": True, "reason": "no_lines_in_draft"}

    idx = _nearest_week_index(lines, event_date)

    ln = lines[idx]
    note_parts = []
    if ln.nota:
        note_parts.append(ln.nota)
    if set_pp is not None:
        ln.pp_g = round(float(set_pp), 3)
        note_parts.append(f"obs_pp:{reason}")
    if set_sob is not None:
        sob_val = max(0.0, min(100.0, float(set_sob)))
        ln.sob_pct_linea = round(sob_val, 2)
        note_parts.append(f"obs_sob:{reason}")
    ln.nota = " | ".join(note_parts) if note_parts else None

    pp_series = [float(x.pp_g) for x in lines]
    sob_series = [float(x.sob_pct_linea) for x in lines]

    pp_anchors = _anchor_indexes(lines, "obs_pp:")
    sob_anchors = _anchor_indexes(lines, "obs_sob:")

    _interpolate_series(pp_series, pp_anchors, shape="s_curve")
    _interpolate_series(sob_series, sob_anchors, shape="linear")

    for i, l in enumerate(lines):
        l.pp_g = round(pp_series[i], 3)
        l.sob_pct_linea = round(max(0.0, min(100.0, sob_series[i])), 2)

    increments = _recalc_increments(pp_series)
    for i, l in enumerate(lines):
        l.incremento_g_sem = increments[i]

    draft.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "skipped": False,
        "ciclo_id": ciclo_id,
        "proyeccion_id": draft.proyeccion_id,
        "week_idx": int(idx),
        "anchored": {
            "pp": set_pp is not None,
            "sob": set_sob is not None,
            "reason": reason,
            "event_date": event_date,
        },
        "lines_rebuilt": len(lines),
    }


def observe_and_rebuild_hook_safe(
    db: Session,
    user: Usuario,
    ciclo_id: int,
    *,
    event_date: date,
    set_pp: Optional[float],
    set_sob: Optional[float],
    reason: str,
) -> None:
    try:
        observe_and_rebuild(
            db, user, ciclo_id,
            event_date=event_date,
            set_pp=set_pp,
            set_sob=set_sob,
            reason=reason,
            soft_if_other_draft=True,
        )
    except Exception:
        pass


# -------- Agregación ponderada (ventana y fin de semana) --------

def _siembra_plan_for_cycle(db: Session, ciclo_id: int) -> Optional[SiembraPlan]:
    return db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()


def _densidad_base_org_m2(db: Session, plan: Optional[SiembraPlan], estanque_id: int) -> Optional[Decimal]:
    if not plan:
        return None
    se = (
        db.query(SiembraEstanque)
        .filter(SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
                SiembraEstanque.estanque_id == estanque_id)
        .first()
    )
    if se and se.densidad_override_org_m2 is not None:
        ov = Decimal(str(se.densidad_override_org_m2))
        if ov > 0:
            return ov
    if plan.densidad_org_m2 is not None:
        pv = Decimal(str(plan.densidad_org_m2))
        if pv > 0:
            return pv
    return None


def _densidad_retirada_acum_org_m2(db: Session, ciclo_id: int, estanque_id: int) -> Decimal:
    plan = db.query(PlanCosechas).filter(PlanCosechas.ciclo_id == ciclo_id).first()
    if not plan:
        return Decimal("0.0000")
    total = (
        db.query(func.coalesce(func.sum(CosechaEstanque.densidad_retirada_org_m2), 0))
        .join(CosechaOla, CosechaEstanque.cosecha_ola_id == CosechaOla.cosecha_ola_id)
        .filter(
            CosechaOla.plan_cosechas_id == plan.plan_cosechas_id,
            CosechaEstanque.estanque_id == estanque_id,
            CosechaEstanque.estado == "c",
        )
        .scalar()
    )
    return Decimal(str(total or 0))


def _ponds_in_cycle(db: Session, ciclo_id: int) -> List[Estanque]:
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        return []
    return (
        db.query(Estanque)
        .filter(Estanque.granja_id == ciclo.granja_id)
        .order_by(asc(Estanque.estanque_id))
        .all()
    )


def _aggregate_window_pp_sob(
    db: Session,
    ciclo_id: int,
    start_date: date,
    end_date: date,
) -> Dict[str, Any]:
    ponds = _ponds_in_cycle(db, ciclo_id)
    total = len(ponds)
    if total == 0:
        return {"pp": None, "sob": None, "coverage": 0.0, "measured": 0, "total": 0}

    plan_s = _siembra_plan_for_cycle(db, ciclo_id)

    pp_x = Decimal("0")
    pp_w = Decimal("0")
    sob_x = Decimal("0")
    sob_w = Decimal("0")

    measured = 0

    for pond in ponds:
        bio = (
            db.query(Biometria)
            .filter(
                Biometria.ciclo_id == ciclo_id,
                Biometria.estanque_id == pond.estanque_id,
                Biometria.fecha >= start_date,
                Biometria.fecha <= end_date,
            )
            .order_by(Biometria.created_at.is_(None).asc(), desc(Biometria.created_at))
            .first()
        )
        if not bio:
            continue

        measured += 1

        dens_base = _densidad_base_org_m2(db, plan_s, pond.estanque_id)
        if dens_base is None or pond.superficie_m2 is None:
            continue

        dens_retirada = _densidad_retirada_acum_org_m2(db, ciclo_id, pond.estanque_id)
        dens_rem = dens_base - dens_retirada
        if dens_rem < Decimal("0"):
            dens_rem = Decimal("0")

        area = Decimal(str(pond.superficie_m2))

        base_weight = dens_rem * area

        if bio.sob_usada_pct is not None:
            sob_val = Decimal(str(bio.sob_usada_pct))
            sob_x += sob_val * base_weight
            sob_w += base_weight

        if bio.pp_g is not None and bio.sob_usada_pct is not None:
            org_est = base_weight * (Decimal(str(bio.sob_usada_pct)) / Decimal("100"))
            pp_x += Decimal(str(bio.pp_g)) * org_est
            pp_w += org_est

    pp = float((pp_x / pp_w)) if pp_w > 0 else None
    sob = float((sob_x / sob_w)) if sob_w > 0 else None
    coverage = measured / total if total > 0 else 0.0

    return {
        "pp": pp,
        "sob": sob,
        "coverage": coverage,
        "measured": measured,
        "total": total,
    }


# -------- Nuevo: modo FIN DE SEMANA (Sábado-Domingo) --------

def _weekend_window_for(event_date: date) -> Tuple[date, date, date]:
    """
    Devuelve (sabado, domingo, anchor=domingo) para el "week" de event_date.
    Semana inicia en lunes (weekday 0).
    """
    monday = event_date - timedelta(days=event_date.weekday())  # lunes de esa semana
    saturday = monday + timedelta(days=5)
    sunday = monday + timedelta(days=6)
    anchor = sunday
    return saturday, sunday, anchor


def observe_and_rebuild_from_weekend_window(
    db: Session,
    user: Usuario,
    ciclo_id: int,
    *,
    event_date: date,
    coverage_threshold: float = COVERAGE_THRESHOLD_DEFAULT,
    min_ponds: int = MIN_PONDS_FOR_COVERAGE_DEFAULT,
    reason: str = "bio_weekend_agg",
    soft_if_other_draft: bool = True,
) -> dict:
    """
    Agrega biometrías del fin de semana (Sábado-Domingo) de event_date,
    pondera a nivel granja y ancla en DOMINGO si hay cobertura suficiente.
    """
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    start, end, anchor = _weekend_window_for(event_date)
    agg = _aggregate_window_pp_sob(db, ciclo_id, start, end)

    if agg["total"] == 0:
        return {"skipped": True, "reason": "no_ponds", "window": (start, end), "agg": agg}
    if agg["measured"] < max(min_ponds, 1):
        return {"skipped": True, "reason": "below_min_ponds", "window": (start, end), "agg": agg}
    if agg["coverage"] < coverage_threshold:
        return {"skipped": True, "reason": "below_coverage_threshold", "window": (start, end), "agg": agg}

    set_pp = agg["pp"]
    set_sob = agg["sob"]
    if set_pp is None and set_sob is None:
        return {"skipped": True, "reason": "no_aggregated_values", "window": (start, end), "agg": agg}

    res = observe_and_rebuild(
        db, user, ciclo_id,
        event_date=anchor,       # anclar en DOMINGO
        set_pp=set_pp,
        set_sob=set_sob,
        reason=reason,
        soft_if_other_draft=soft_if_other_draft,
    )
    res["agg"] = agg
    res["window"] = (start, end)
    res["anchor"] = anchor
    return res


def observe_and_rebuild_from_weekend_window_hook_safe(
    db: Session,
    user: Usuario,
    ciclo_id: int,
    *,
    event_date: date,
    coverage_threshold: float = COVERAGE_THRESHOLD_DEFAULT,
    min_ponds: int = MIN_PONDS_FOR_COVERAGE_DEFAULT,
    reason: str = "bio_weekend_agg",
) -> None:
    try:
        observe_and_rebuild_from_weekend_window(
            db, user, ciclo_id,
            event_date=event_date,
            coverage_threshold=coverage_threshold,
            min_ponds=min_ponds,
            reason=reason,
            soft_if_other_draft=True,
        )
    except Exception:
        # silenciar; puedes loggear
        pass


# -------- (Opcional) modo ventana libre que ya teníamos --------

def observe_and_rebuild_from_window(
    db: Session,
    user: Usuario,
    ciclo_id: int,
    *,
    event_date: date,
    window_radius_days: int = WINDOW_RADIUS_DAYS_DEFAULT,
    coverage_threshold: float = COVERAGE_THRESHOLD_DEFAULT,
    min_ponds: int = MIN_PONDS_FOR_COVERAGE_DEFAULT,
    reason: str = "bio_agg",
    soft_if_other_draft: bool = True,
) -> dict:
    start = event_date - timedelta(days=window_radius_days)
    end = event_date + timedelta(days=window_radius_days)

    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    agg = _aggregate_window_pp_sob(db, ciclo_id, start, end)
    if agg["total"] == 0:
        return {"skipped": True, "reason": "no_ponds", "agg": agg}

    if agg["measured"] < max(min_ponds, 1):
        return {"skipped": True, "reason": "below_min_ponds", "agg": agg}

    if agg["coverage"] < coverage_threshold:
        return {"skipped": True, "reason": "below_coverage_threshold", "agg": agg}

    set_pp = agg["pp"]
    set_sob = agg["sob"]
    if set_pp is None and set_sob is None:
        return {"skipped": True, "reason": "no_aggregated_values", "agg": agg}

    res = observe_and_rebuild(
        db, user, ciclo_id,
        event_date=event_date,
        set_pp=set_pp,
        set_sob=set_sob,
        reason=reason,
        soft_if_other_draft=soft_if_other_draft,
    )
    res["agg"] = agg
    return res


def observe_and_rebuild_from_window_hook_safe(
    db: Session,
    user: Usuario,
    ciclo_id: int,
    *,
    event_date: date,
    window_radius_days: int = WINDOW_RADIUS_DAYS_DEFAULT,
    coverage_threshold: float = COVERAGE_THRESHOLD_DEFAULT,
    min_ponds: int = MIN_PONDS_FOR_COVERAGE_DEFAULT,
    reason: str = "bio_agg",
) -> None:
    try:
        observe_and_rebuild_from_window(
            db, user, ciclo_id,
            event_date=event_date,
            window_radius_days=window_radius_days,
            coverage_threshold=coverage_threshold,
            min_ponds=min_ponds,
            reason=reason,
            soft_if_other_draft=True,
        )
    except Exception:
        pass
