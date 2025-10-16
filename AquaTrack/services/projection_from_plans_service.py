# /services/projection_from_plans_service.py
from __future__ import annotations
from datetime import date, timedelta, datetime, timezone
from typing import List, Tuple, Dict
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, asc
from types import SimpleNamespace

from models.ciclo import Ciclo
from models.siembra_plan import SiembraPlan
from models.plan_cosechas import PlanCosechas
from models.cosecha_ola import CosechaOla
from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from models.usuario import Usuario

from services.permissions_service import ensure_user_in_farm_or_admin, require_scopes
from schemas.proyeccion import ProyeccionFromPlansIn

# Usar SIEMPRE tus servicios existentes de cosecha
from services.harvest_service import (
    get_plan as hv_get_plan,
    upsert_plan as hv_upsert_plan,
    upsert_wave as hv_upsert_wave,
    generate_pond_harvests as hv_generate_pond_harvests,
)
from services.projection_service import _autopublish_if_first


# --------------------------------- helpers --------------------------------- #

def _next_version_for_cycle(db: Session, ciclo_id: int) -> str:
    cnt = db.query(func.count(Proyeccion.proyeccion_id)).filter(Proyeccion.ciclo_id == ciclo_id).scalar() or 0
    return f"v{cnt + 1}"

def _smooth_factor(t: float, shape: str) -> float:
    t = max(0.0, min(1.0, t))
    if shape == "linear":
        return t
    if shape == "ease_in":
        return t * t
    if shape == "ease_out":
        return 1 - (1 - t) * (1 - t)
    return 3 * (t ** 2) - 2 * (t ** 3)  # s_curve

def _weekly_dates(start: date, weeks: int) -> List[date]:
    return [start + timedelta(days=7 * i) for i in range(weeks)]

def _week_index_for_date(start: date, target: date, weeks: int) -> int:
    """Redondea al índice de semana más cercano a target (clamp 0..weeks-1)."""
    days = (target - start).days
    idx = int(round(days / 7.0))
    if idx < 0:
        idx = 0
    if idx > weeks - 1:
        idx = weeks - 1
    return idx

def _derive_cosechas_from_waves(
    db: Session, user: Usuario, ciclo_id: int, start_date: date, weeks: int
) -> Dict[int, Dict[str, object]]:
    """
    Lee plan_cosechas -> olas y arma un mapa {semana_idx: {retiro_org_m2, final}}
    usando ventana_fin como referencia de flag. final=True si ola.tipo=='f'.
    """
    plan = hv_get_plan(db, user, ciclo_id)
    if not plan:
        return {}

    olas = (
        db.query(CosechaOla)
        .filter(CosechaOla.plan_cosechas_id == plan.plan_cosechas_id)
        .order_by(asc(CosechaOla.ventana_fin), asc(CosechaOla.orden))
        .all()
    )
    if not olas:
        return {}

    cosecha_map: Dict[int, Dict[str, object]] = {}
    for o in olas:
        idx = _week_index_for_date(start_date, o.ventana_fin, weeks)
        cosecha_map[idx] = {
            "retiro_org_m2": (float(o.objetivo_retiro_org_m2) if o.objetivo_retiro_org_m2 is not None else None),
            "final": (o.tipo == "f"),
        }
    return cosecha_map


# --------------------------------- servicio --------------------------------- #

def generate_from_plans(
    db: Session,
    user: Usuario,
    *,
    ciclo_id: int,
    payload: ProyeccionFromPlansIn,
) -> Tuple[Proyeccion, List[str]]:
    """
    Genera una proyección tipo 'borrador' usando:
    - start_date: payload.start_date o SiembraPlan.ventana_fin (si use_existing_seeding_plan=True).
    - pp_inicial_g: payload.curva.pp_inicial_g o SiembraPlan.talla_inicial_g o 0.
    - Curva PP (shape) y SOB objetivo al final.
    - Flags de cosecha:
        * Si payload.cosechas existe -> prioridad para la proyección.
        * Si NO existe y use_existing_harvest_plan=True -> derivamos de CosechaOla usando ventana_fin.
    - EXTRA: si payload.cosechas viene y NO hay Plan de Cosechas en el ciclo,
             se crea automáticamente el Plan + Olas + Cosechas por estanque, usando harvest_service.
    """
    warnings: List[str] = []

    # 1) ciclo + permisos
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)
    require_scopes(db, user, ciclo.granja_id, {"projections:create"})

    # 2) SiembraPlan para defaults
    sp = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()

    # 3) start_date
    start_date = payload.start_date
    if start_date is None and payload.use_existing_seeding_plan:
        if not sp:
            raise HTTPException(status_code=422, detail="start_date_required_without_seeding_plan")
        start_date = sp.ventana_fin
    if start_date is None:
        raise HTTPException(status_code=422, detail="start_date_required")

    # 4) parámetros de curva
    weeks = payload.curva.semanas
    if weeks < 1:
        raise HTTPException(status_code=422, detail="weeks_must_be_positive")

    pp0 = payload.curva.pp_inicial_g
    if pp0 is None and payload.use_existing_seeding_plan and sp and (sp.talla_inicial_g is not None):
        pp0 = float(sp.talla_inicial_g)
    if pp0 is None:
        pp0 = 0.0

    ppF = float(payload.curva.peso_final_objetivo_g)
    sobF = float(payload.curva.sob_final_objetivo_pct)
    shape = payload.curva.shape

    # clamp sob objetivo
    if sobF < 0:
        sobF = 0.0
    if sobF > 100:
        sobF = 100.0

    # 5) construir fechas y series
    dates = _weekly_dates(start_date, weeks)

    # PP interpolado por shape
    lines_pp: List[float] = []
    for i in range(weeks):
        t = 0.0 if weeks == 1 else i / (weeks - 1)
        f = _smooth_factor(t, shape)
        pp = pp0 + f * (ppF - pp0)
        lines_pp.append(round(pp, 3))

    # incremento_g_sem
    increments: List[float] = []
    for i in range(weeks):
        if i == 0:
            increments.append(round(lines_pp[0], 3))
        else:
            increments.append(round(lines_pp[i] - lines_pp[i - 1], 3))

    # SOB lineal 100 -> sobF
    lines_sob: List[float] = []
    sob0 = 100.0
    for i in range(weeks):
        t = 0.0 if weeks == 1 else i / (weeks - 1)
        sob = sob0 + t * (sobF - sob0)
        if sob < 0:
            sob = 0.0
        if sob > 100:
            sob = 100.0
        lines_sob.append(round(sob, 2))

    # 6) flags de cosecha (para la PROYECCIÓN)
    cosecha_map: Dict[int, Dict[str, object]] = {}

    # a) Derivar desde plan de cosechas si aplica (solo si no vienen en payload)
    if payload.cosechas is None and payload.use_existing_harvest_plan:
        derived = _derive_cosechas_from_waves(db, user, ciclo_id, start_date, weeks)
        cosecha_map.update(derived)

    # b) Aplicar manuales si vienen (tienen prioridad sobre lo derivado)
    if payload.cosechas:
        for flag in payload.cosechas:
            if flag.semana_idx < 0 or flag.semana_idx >= weeks:
                warnings.append(f"cosecha_flag_out_of_range_semana_idx={flag.semana_idx}")
                continue
            cosecha_map[flag.semana_idx] = {
                "retiro_org_m2": flag.retiro_org_m2,
                "final": flag.final,
            }

    # 6.1) (EXTRA) Si NO hay Plan de Cosechas y sí vienen flags en el payload -> crear Plan + Olas + CosechasxEstanque
    plan_created = False
    waves_created = 0
    if payload.cosechas:
        existing_plan = hv_get_plan(db, user, ciclo_id)
        if existing_plan is None:
            # Necesitamos permisos de harvest:plan para crear
            require_scopes(db, user, ciclo.granja_id, {"harvest:plan"})

            # Crear plan
            plan = hv_upsert_plan(db, user, ciclo_id, nota_operativa="Autogenerado desde proyección (payload)")
            plan_created = True

            # Crear olas usando la convención: ventana_inicio = fecha semana anterior, ventana_fin = fecha en el flag
            # tipo 'f' si flag.final True, o si es el último flag y final es None.
            ordered_flags = sorted(payload.cosechas, key=lambda f: f.semana_idx)
            last_index = len(ordered_flags) - 1

            for i, flag in enumerate(ordered_flags):
                if flag.semana_idx < 0 or flag.semana_idx >= weeks:
                    continue  # ya registramos warning arriba

                v_fin = dates[flag.semana_idx]
                v_ini = dates[flag.semana_idx - 1] if flag.semana_idx > 0 else dates[0]

                is_final = bool(flag.final) if flag.final is not None else (i == last_index)
                tipo = "f" if is_final else "p"
                nombre = "Final" if is_final else f"Ola {i + 1}"

                wave_body = SimpleNamespace(
                    nombre=nombre,
                    tipo=tipo,
                    ventana_inicio=v_ini,
                    ventana_fin=v_fin,
                    objetivo_retiro_org_m2=flag.retiro_org_m2,
                    estado="p",
                    orden=flag.semana_idx,
                    notas="Autogenerada desde proyección (payload)",
                )
                ola = hv_upsert_wave(db, user, plan.plan_cosechas_id, wave_body)
                hv_generate_pond_harvests(db, user, ola.cosecha_ola_id)
                waves_created += 1

            warnings.append(f"harvest_plan_autocreated=True waves_created={waves_created}")

    # 7) crear proyección borrador
    version = _next_version_for_cycle(db, ciclo_id)
    proy = Proyeccion(
        ciclo_id=ciclo_id,
        version=version,
        descripcion="Borrador generado desde planes (curvas objetivo)",
        status="b",
        is_current=False,
        creada_por=user.usuario_id,
        source_type="planes",
        source_ref=None,
        sob_final_objetivo_pct=sobF,
        siembra_ventana_fin=start_date,
    )
    db.add(proy)
    db.flush()  # proyeccion_id

    # 8) insertar líneas
    bulk = []
    for i in range(weeks):
        cosecha_flag = i in cosecha_map
        retiro_org_m2 = None
        if cosecha_flag:
            retiro_org_m2 = cosecha_map[i].get("retiro_org_m2")

        bulk.append(
            ProyeccionLinea(
                proyeccion_id=proy.proyeccion_id,
                edad_dias=i * 7,
                semana_idx=i,
                fecha_plan=dates[i],
                pp_g=lines_pp[i],
                incremento_g_sem=increments[i],
                sob_pct_linea=lines_sob[i],
                cosecha_flag=cosecha_flag,
                retiro_org_m2=retiro_org_m2,
                nota=None,
            )
        )
    if bulk:
        db.bulk_save_objects(bulk)

    db.commit()
    db.refresh(proy)

    # Autopublish si es la primera del ciclo
    if _autopublish_if_first(db, proy):
        warnings.append("auto_published=True (first_projection_in_cycle)")
    else:
        warnings.append("auto_published=False (current_projection_already_exists)")

    # Mensaje informativo si se autogeneró plan/olas
    if plan_created:
        warnings.append("harvest_ponds_generated=YES")

    return proy, warnings
