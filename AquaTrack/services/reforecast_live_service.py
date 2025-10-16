# services/reforecast_live_service.py
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Optional, List, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func

from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from models.ciclo import Ciclo
from models.usuario import Usuario
from services.permissions_service import ensure_user_in_farm_or_admin


# -------- helpers --------

def _smooth_factor(t: float, shape: str = "s_curve") -> float:
    # clamp
    t = max(0.0, min(1.0, t))
    if shape == "linear":
        return t
    if shape == "ease_in":
        return t * t
    if shape == "ease_out":
        return 1 - (1 - t) * (1 - t)
    # default s-curve
    return 3 * (t ** 2) - 2 * (t ** 3)


def _nearest_week_index(lines: List[ProyeccionLinea], when: date) -> int:
    # asume lines ordenadas por fecha_plan asc
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


def _anchor_indexes(
    lines: List[ProyeccionLinea],
    tag_prefix: str,  # 'obs_pp:' o 'obs_sob:'
) -> List[int]:
    idxs = set()
    for i, l in enumerate(lines):
        if l.nota and tag_prefix in l.nota:
            idxs.add(i)
    # siempre considerar extremos como anclas
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


# -------- API principal del servicio --------

def ensure_reforecast_draft(
    db: Session,
    user: Usuario,
    ciclo_id: int,
    *,
    soft_if_other_draft: bool = False,
) -> Optional[Proyeccion]:
    """
    - Si existe draft 'reforecast' -> devolverlo.
    - Si NO existe y no hay otro draft -> clonar desde vigente y devolverlo.
    - Si hay otro draft (no reforecast):
        * soft_if_other_draft=True -> devolver None (no interferir).
        * soft_if_other_draft=False -> 409.
    """
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

    # ¿hay cualquier otro draft?
    other = (
        db.query(Proyeccion)
        .filter(
            Proyeccion.ciclo_id == ciclo_id,
            Proyeccion.status == "b",
        )
        .first()
    )
    if other:
        if soft_if_other_draft:
            return None
        raise HTTPException(status_code=409, detail="draft_projection_already_exists")

    # crear desde vigente
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
    """
    Fija anclas PP/SOB en la línea más cercana a `event_date` y reinterpola todo el draft reforecast.
    """
    if set_pp is None and set_sob is None:
        raise HTTPException(status_code=422, detail="at_least_one_of_pp_or_sob_required")

    draft = ensure_reforecast_draft(db, user, ciclo_id, soft_if_other_draft=soft_if_other_draft)
    if draft is None:
        # soft mode: no interferir si existe otro borrador
        return {"skipped": True, "reason": "another_draft_exists"}

    lines: List[ProyeccionLinea] = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx), asc(ProyeccionLinea.fecha_plan))
        .all()
    )
    if not lines:
        return {"skipped": True, "reason": "no_lines_in_draft"}

    # ancla más cercana a la fecha
    idx = _nearest_week_index(lines, event_date)

    # fijar observaciones en la línea idx
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

    # preparar series actuales
    pp_series = [float(x.pp_g) for x in lines]
    sob_series = [float(x.sob_pct_linea) for x in lines]

    # anclas detectadas
    pp_anchors = _anchor_indexes(lines, "obs_pp:")
    sob_anchors = _anchor_indexes(lines, "obs_sob:")

    # reinterpolar (PP s-curve, SOB lineal)
    _interpolate_series(pp_series, pp_anchors, shape="s_curve")
    _interpolate_series(sob_series, sob_anchors, shape="linear")

    # escribir de vuelta
    for i, l in enumerate(lines):
        l.pp_g = round(pp_series[i], 3)
        l.sob_pct_linea = round(max(0.0, min(100.0, sob_series[i])), 2)

    # incrementos
    increments = _recalc_increments(pp_series)
    for i, l in enumerate(lines):
        l.incremento_g_sem = increments[i]

    # toque al draft (updated_at ya está con server_default onupdate)
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


# -------- versión segura para hooks (no romper flujo operativo) --------

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
        # swallow: no interrumpir operación
        # (puedes loggear con tu logger si lo tienes)
        pass
