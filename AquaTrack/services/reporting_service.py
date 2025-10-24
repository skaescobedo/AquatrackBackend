from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, or_

from zoneinfo import ZoneInfo

from config.settings import settings
from models.usuario import Usuario
from models.ciclo import Ciclo
from models.estanque import Estanque
from models.siembra_plan import SiembraPlan
from models.siembra_estanque import SiembraEstanque
from models.plan_cosechas import PlanCosechas
from models.cosecha_ola import CosechaOla
from models.cosecha_estanque import CosechaEstanque
from models.biometria import Biometria
from models.sob_cambio_log import SobCambioLog
from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea

from services.permissions_service import ensure_user_in_farm_or_admin


# -------- helpers de zona horaria / fecha --------

def _get_tz(tz_name: Optional[str]) -> ZoneInfo:
    try:
        name = tz_name or settings.DEFAULT_TZ or "UTC"
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def _today_local_date(tz: ZoneInfo) -> date:
    # "Hoy" respecto a la zona horaria dada
    return datetime.now(tz).date()


def _now_utc() -> datetime:
    # Se mantiene por compatibilidad; si necesitas "ahora" en tz, usa datetime.now(tz)
    return datetime.now(timezone.utc)


def _as_tz(dt: Optional[datetime], tz: ZoneInfo) -> Optional[datetime]:
    """
    Convierte un datetime a la zona dada.
    - Si dt es naive, se asume que está en la zona de la BD (settings.DB_TZ) y se convierte a tz.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        src = ZoneInfo(getattr(settings, "DB_TZ", settings.DEFAULT_TZ or "UTC"))
        dt = dt.replace(tzinfo=src)
    return dt.astimezone(tz)


def _date_in_tz(dt: datetime, tz: ZoneInfo) -> date:
    """
    Convierte un datetime a la zona dada y devuelve .date().
    - Si dt es naive, se asume que está en la zona de la BD (settings.DB_TZ).
    """
    if dt.tzinfo is None:
        src = ZoneInfo(getattr(settings, "DB_TZ", settings.DEFAULT_TZ or "UTC"))
        dt = dt.replace(tzinfo=src)
    return dt.astimezone(tz).date()


# -------- proyección vigente --------

def _current_projection(db: Session, ciclo_id: int) -> Optional[Proyeccion]:
    # Orden: vigente primero, luego publicadas recientes, luego creadas recientes.
    return (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id)
        .order_by(
            desc(Proyeccion.is_current),
            Proyeccion.published_at.is_(None).asc(),  # sin NULLS LAST
            desc(Proyeccion.published_at),
            desc(Proyeccion.created_at),
        )
        .first()
    )


def _line_for_today(db: Session, proyeccion_id: int, today: date) -> Optional[ProyeccionLinea]:
    """
    Elegir la línea de proyección más cercana a 'today' (pasado o futuro).
    """
    prev_line = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == proyeccion_id,
                ProyeccionLinea.fecha_plan <= today)
        .order_by(desc(ProyeccionLinea.fecha_plan))
        .first()
    )
    next_line = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == proyeccion_id,
                ProyeccionLinea.fecha_plan >= today)
        .order_by(asc(ProyeccionLinea.fecha_plan))
        .first()
    )
    if prev_line and next_line:
        diff_prev = abs((today - prev_line.fecha_plan).days)
        diff_next = abs((next_line.fecha_plan - today).days)
        return prev_line if diff_prev <= diff_next else next_line
    return prev_line or next_line


# -------- SOB y PP vigentes --------

def _current_operational_sob_pct(
    db: Session, ciclo_id: int, estanque_id: int, today: date
) -> Tuple[Optional[Decimal], Optional[str]]:
    # 1) última operativa (sob_cambio_log)
    last_log = (
        db.query(SobCambioLog)
        .filter(SobCambioLog.ciclo_id == ciclo_id, SobCambioLog.estanque_id == estanque_id)
        .order_by(SobCambioLog.changed_at.is_(None).asc(), desc(SobCambioLog.changed_at))
        .first()
    )
    if last_log:
        return Decimal(str(last_log.sob_nueva_pct)), "operativa_actual"

    # 2) proyección vigente
    proj = _current_projection(db, ciclo_id)
    if proj:
        line = _line_for_today(db, proj.proyeccion_id, today)
        if line:
            return Decimal(str(line.sob_pct_linea)), "reforecast"

    return None, None


def _current_pp_g(
    db: Session, ciclo_id: int, estanque_id: int, today: date, tz: ZoneInfo
) -> Tuple[Optional[Decimal], Optional[str], Optional[datetime]]:
    """
    Devuelve (pp_g, fuente, timestamp_en_tz).
    Si el timestamp viene naive, se interpreta como settings.DB_TZ y se convierte a tz.
    """
    last_bio = (
        db.query(Biometria)
        .filter(Biometria.ciclo_id == ciclo_id, Biometria.estanque_id == estanque_id)
        .order_by(Biometria.created_at.is_(None).asc(), desc(Biometria.created_at))
        .first()
    )
    if last_bio:
        return Decimal(str(last_bio.pp_g)), "biometria", _as_tz(last_bio.created_at, tz)

    proj = _current_projection(db, ciclo_id)
    if proj:
        line = _line_for_today(db, proj.proyeccion_id, today)
        if line:
            return Decimal(str(line.pp_g)), "proyeccion", None

    return None, None, None


# -------- densidades --------

def _siembra_plan_for_cycle(db: Session, ciclo_id: int) -> Optional[SiembraPlan]:
    return db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()


def _densidad_base_org_m2(db: Session, plan: Optional[SiembraPlan], estanque_id: int) -> Optional[Decimal]:
    """
    Solo usar override si es > 0; si no, caer a plan si es > 0; de lo contrario, None.
    """
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


def _densidad_retirada_acum_org_m2(
    db: Session, ciclo_id: int, estanque_id: int
) -> Decimal:
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


# -------- cálculo por estanque --------

def _pond_operational_row(
    *,
    estanque: Estanque,
    dens_base: Optional[Decimal],
    dens_retirada: Decimal,
    sob_pct: Optional[Decimal],
    sob_fuente: Optional[str],
    pp_g: Optional[Decimal],
    pp_fuente: Optional[str],
    pp_timestamp: Optional[datetime],
) -> Optional[Dict[str, Any]]:
    if dens_base is None:
        return None

    dens_rem = dens_base - dens_retirada
    if dens_rem < Decimal("0"):
        dens_rem = Decimal("0")

    # Densidad viva = remanente × SOB%
    dens_viva_org_m2 = None
    org_vivos_est = None
    biomasa_est_kg = None

    sup_dec = Decimal(str(estanque.superficie_m2))

    if sob_pct is not None:
        dens_viva_org_m2 = (dens_rem * (sob_pct / Decimal("100"))).quantize(Decimal("0.0001"))
        org_vivos_est = (dens_viva_org_m2 * sup_dec).quantize(Decimal("0.0001"))

    if org_vivos_est is not None and pp_g is not None:
        biomasa_est_kg = (org_vivos_est * (pp_g / Decimal("1000"))).quantize(Decimal("0.1"))

    return {
        "estanque_id": int(estanque.estanque_id),
        "nombre": estanque.nombre,
        "superficie_m2": float(estanque.superficie_m2),
        "densidad_base_org_m2": float(dens_base),
        "densidad_retirada_acum_org_m2": float(dens_retirada),
        # Ya no devolvemos densidad_remanente_org_m2 en el response
        "densidad_viva_org_m2": float(dens_viva_org_m2) if dens_viva_org_m2 is not None else None,
        "sob_vigente_pct": float(sob_pct) if sob_pct is not None else None,
        "sob_fuente": sob_fuente,
        "pp_vigente_g": float(pp_g) if pp_g is not None else None,
        "pp_fuente": pp_fuente,
        "pp_updated_at": pp_timestamp,  # ya viene convertido a tz si venía de biometría
        "org_vivos_est": float(org_vivos_est) if org_vivos_est is not None else None,
        "biomasa_est_kg": float(biomasa_est_kg) if biomasa_est_kg is not None else None,
    }


# -------- KPIs agregados (ponderaciones) --------

def _aggregate_kpis(pond_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    superficies = Decimal("0")
    dens_viva_x_sup = Decimal("0")

    # Para SOB global (vivos / remanente pre-SOB)
    total_vivos_all = Decimal("0")
    total_rem_pre_sob = Decimal("0")

    # Para PP promedio (mini-fix: solo vivos con PP)
    pp_x_org = Decimal("0")
    org_vivos_tot_for_pp = Decimal("0")

    biomasa_total = Decimal("0")

    ponds_with_dens = 0
    ponds_with_org = 0

    for r in pond_rows:
        sup = Decimal(str(r["superficie_m2"])) if r.get("superficie_m2") is not None else None

        # Promedio de densidad viva ponderado por superficie
        if r.get("densidad_viva_org_m2") is not None and sup is not None:
            dens_viva = Decimal(str(r["densidad_viva_org_m2"]))
            superficies += sup
            dens_viva_x_sup += (dens_viva * sup)
            ponds_with_dens += 1

        # Acumuladores de vivos / biomasa
        if r.get("org_vivos_est") is not None:
            org = Decimal(str(r["org_vivos_est"]))
            total_vivos_all += org
            ponds_with_org += 1

        if r.get("biomasa_est_kg") is not None:
            biomasa_total += Decimal(str(r["biomasa_est_kg"]))

        # Mini-fix PP: solo ponderar por vivos de estanques con PP
        if r.get("pp_vigente_g") is not None and r.get("org_vivos_est") is not None:
            pp = Decimal(str(r["pp_vigente_g"]))
            org = Decimal(str(r["org_vivos_est"]))
            pp_x_org += (pp * org)
            org_vivos_tot_for_pp += org

        # Reconstruir remanente pre-SOB para SOB global
        if (
            r.get("densidad_viva_org_m2") is not None and
            r.get("sob_vigente_pct") not in (None, 0) and
            sup is not None
        ):
            dens_viva = Decimal(str(r["densidad_viva_org_m2"]))
            sob = Decimal(str(r["sob_vigente_pct"]))
            # rem_dens = dens_viva / (sob/100)
            rem_dens = dens_viva / (sob / Decimal("100"))
            total_rem_pre_sob += (rem_dens * sup)

    dens_viva_prom = (dens_viva_x_sup / superficies) if superficies > 0 else None

    # SOB global (tu lógica deseada), mantenemos el nombre del campo de salida
    sob_global = (total_vivos_all / total_rem_pre_sob * Decimal("100")) if total_rem_pre_sob > 0 else None

    # PP promedio con mini-fix
    pp_prom = (pp_x_org / org_vivos_tot_for_pp) if org_vivos_tot_for_pp > 0 else None

    return {
        "biomasa_estim_kg": float(biomasa_total.quantize(Decimal("0.1"))),
        "densidad_viva_org_m2": float(dens_viva_prom.quantize(Decimal("0.0001"))) if dens_viva_prom is not None else None,
        "sob_vigente_prom_pct": float(sob_global.quantize(Decimal("0.01"))) if sob_global is not None else None,
        "pp_vigente_prom_g": float(pp_prom.quantize(Decimal("0.01"))) if pp_prom is not None else None,
        "sample_sizes": {
            "ponds_total": len(pond_rows),
            "ponds_with_density": ponds_with_dens,  # cuenta estanques con densidad viva calculada
            "ponds_with_org_vivos": ponds_with_org,
        }
    }


# -------- progresos (siembra/cosecha) --------

def _progress_siembras(db: Session, ciclo_id: int) -> Tuple[Optional[float], Dict[str, int]]:
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        return None, {"confirmadas": 0, "total": 0}
    total = db.query(SiembraEstanque).filter(SiembraEstanque.siembra_plan_id == plan.siembra_plan_id).count()
    conf = db.query(SiembraEstanque).filter(
        SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
        SiembraEstanque.estado == "f",
    ).count()
    pct = (conf / total * 100.0) if total > 0 else None
    return pct, {"confirmadas": conf, "total": total}


def _progress_cosechas(db: Session, ciclo_id: int) -> Tuple[Optional[float], Dict[str, int]]:
    plan = db.query(PlanCosechas).filter(PlanCosechas.ciclo_id == ciclo_id).first()
    if not plan:
        return None, {"estanques_con_planeacion": 0, "estanques_con_confirmada": 0}
    denom = (
        db.query(func.count(func.distinct(CosechaEstanque.estanque_id)))
        .join(CosechaOla, CosechaEstanque.cosecha_ola_id == CosechaOla.cosecha_ola_id)
        .filter(CosechaOla.plan_cosechas_id == plan.plan_cosechas_id,
                or_(CosechaEstanque.estado == "p", CosechaEstanque.estado == "c"))
        .scalar()
    ) or 0
    numer = (
        db.query(func.count(func.distinct(CosechaEstanque.estanque_id)))
        .join(CosechaOla, CosechaEstanque.cosecha_ola_id == CosechaOla.cosecha_ola_id)
        .filter(CosechaOla.plan_cosechas_id == plan.plan_cosechas_id,
                CosechaEstanque.estado == "c")
        .scalar()
    ) or 0
    pct = (numer / denom * 100.0) if denom > 0 else None
    return pct, {"estanques_con_planeacion": denom, "estanques_con_confirmada": numer}


# -------- olas próximas (7 días) y alertas --------

def _upcoming_waves(db: Session, ciclo_id: int, today: date) -> List[Dict[str, Any]]:
    plan = db.query(PlanCosechas).filter(PlanCosechas.ciclo_id == ciclo_id).first()
    if not plan:
        return []
    horizon = today + timedelta(days=7)
    olas = (
        db.query(CosechaOla)
        .filter(CosechaOla.plan_cosechas_id == plan.plan_cosechas_id)
        .filter(CosechaOla.ventana_inicio <= horizon, CosechaOla.ventana_fin >= today)
        .order_by(asc(CosechaOla.ventana_inicio), asc(CosechaOla.orden))
        .all()
    )
    res = []
    for o in olas:
        pendientes = (
            db.query(func.count(CosechaEstanque.cosecha_estanque_id))
            .filter(CosechaEstanque.cosecha_ola_id == o.cosecha_ola_id,
                    CosechaEstanque.estado == "p")
            .scalar()
        ) or 0
        res.append({
            "ola_id": int(o.cosecha_ola_id),
            "nombre": o.nombre,
            "tipo": o.tipo,
            "ventana_inicio": o.ventana_inicio,
            "ventana_fin": o.ventana_fin,
            "pendientes": int(pendientes),
        })
    return res


def _alerts(
    db: Session,
    ciclo_id: int,
    pond_rows: List[Dict[str, Any]],
    today: date,
    tz: ZoneInfo,
    pp_desvio_threshold_med: float = 10.0,
    pp_desvio_threshold_high: float = 20.0,
    recencia_bio_days_high: int = 14,
    window_days_for_pp_dev: int = 7,  # Gate por cercanía de la proyección
) -> List[Dict[str, Any]]:
    alerts = []

    # 1) recencia de biometría > 14 días (fecha/hora convertida a la zona)
    for r in pond_rows:
        last = (
            db.query(Biometria.created_at)
            .filter(Biometria.ciclo_id == ciclo_id, Biometria.estanque_id == r["estanque_id"])
            .order_by(Biometria.created_at.is_(None).asc(), desc(Biometria.created_at))
            .first()
        )
        if last and last[0]:
            last_date_local = _date_in_tz(last[0], tz)
            days = (today - last_date_local).days
            if days > recencia_bio_days_high:
                alerts.append({
                    "severity": "high",
                    "code": "NO_BIOMETRIA",
                    "estanque_id": r["estanque_id"],
                    "dias": days,
                    "msg": f"Sin biometría > {recencia_bio_days_high} días",
                })

    # 2) desvío PP vigente vs proyección de la semana (si la línea está cerca de hoy)
    proj = _current_projection(db, ciclo_id)
    if proj:
        line = _line_for_today(db, proj.proyeccion_id, today)
        if line and line.pp_g is not None:
            if abs((line.fecha_plan - today).days) <= window_days_for_pp_dev and float(line.pp_g) > 0:
                pp_proj = float(line.pp_g)
                for r in pond_rows:
                    if r.get("pp_vigente_g") is None:
                        continue
                    desvio = (r["pp_vigente_g"] - pp_proj) / pp_proj * 100.0
                    absd = abs(desvio)
                    if absd >= pp_desvio_threshold_high:
                        sev = "high"
                    elif absd >= pp_desvio_threshold_med:
                        sev = "med"
                    else:
                        continue
                    alerts.append({
                        "severity": sev,
                        "code": "PP_DESVIO",
                        "estanque_id": r["estanque_id"],
                        "desvio_pct": round(desvio, 2),
                        "msg": f"PP {'+' if desvio>=0 else ''}{round(desvio,2)}% vs proyección",
                    })

    return alerts


# -------- API principal --------

def operational_state(db: Session, user: Usuario, ciclo_id: int, tz_name: Optional[str] = None) -> Dict[str, Any]:
    tz = _get_tz(tz_name)
    today = _today_local_date(tz)

    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="cycle_not_found")

    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    ponds = (
        db.query(Estanque)
        .filter(Estanque.granja_id == ciclo.granja_id)
        .order_by(asc(Estanque.estanque_id))
        .all()
    )

    plan_s = _siembra_plan_for_cycle(db, ciclo_id)

    pond_rows: List[Dict[str, Any]] = []
    for pond in ponds:
        dens_base = _densidad_base_org_m2(db, plan_s, pond.estanque_id)
        dens_retirada = _densidad_retirada_acum_org_m2(db, ciclo_id, pond.estanque_id)
        sob_pct, sob_src = _current_operational_sob_pct(db, ciclo_id, pond.estanque_id, today)
        pp_g, pp_src, pp_ts = _current_pp_g(db, ciclo_id, pond.estanque_id, today, tz)

        row = _pond_operational_row(
            estanque=pond,
            dens_base=dens_base,
            dens_retirada=dens_retirada,
            sob_pct=sob_pct,
            sob_fuente=sob_src,
            pp_g=pp_g,
            pp_fuente=pp_src,
            pp_timestamp=pp_ts,
        )
        if row is not None:
            pond_rows.append(row)

    kpi = _aggregate_kpis(pond_rows)
    siembras_pct, siembras_counts = _progress_siembras(db, ciclo_id)
    cosechas_pct, cosechas_counts = _progress_cosechas(db, ciclo_id)
    waves = _upcoming_waves(db, ciclo_id, today)
    alerts = _alerts(db, ciclo_id, pond_rows, today, tz)

    proj = _current_projection(db, ciclo_id)
    semana_info = None
    if proj:
        line = _line_for_today(db, proj.proyeccion_id, today)
        if line:
            semana_info = {
                "semana_idx": int(line.semana_idx),
                "fecha_plan": line.fecha_plan,
                "pp_g": float(line.pp_g),
                "sob_pct_linea": float(line.sob_pct_linea),
            }

    return {
        "ciclo_id": ciclo_id,
        "fechas": {
            "inicio": ciclo.fecha_inicio,
            "hoy": today,
        },
        "kpi": {
            **kpi,
            "siembras_avance_pct": siembras_pct,
            "cosechas_avance_pct": cosechas_pct,
            "siembras_counts": siembras_counts,
            "cosechas_counts": cosechas_counts,
        },
        "olas_proximas": waves,
        "alertas": alerts,
        "por_estanque": pond_rows,
        "proyeccion_semana": semana_info,
    }
