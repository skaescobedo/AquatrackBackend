# services/analytics_service.py
"""
Servicio de analytics para preparar datos de dashboards.
Consumido por api/analytics_routes.py

MEJORAS V3:
- Todas las gráficas de ciclo comparan proyección publicada vs borrador
- Nueva gráfica: Curva de SOB (publicado vs borrador)
- Consistencia en estructura de datos entre todas las series temporales
"""
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc

from utils.datetime_utils import today_mazatlan
from models.cycle import Ciclo
from models.pond import Estanque
from models.biometria import Biometria, SOBCambioLog
from models.projection import Proyeccion, ProyeccionLinea, SourceType
from models.seeding import SiembraPlan, SiembraEstanque
from models.harvest import CosechaOla, CosechaEstanque

from services.calculation_service import (
    calculate_densidad_viva,
    calculate_org_vivos,
    calculate_biomasa_kg,
    calculate_weighted_density,
    calculate_global_sob,
    calculate_weighted_pp,
    calculate_total_biomass,
    calculate_deviation_pct,
    calculate_growth_rate
)


# ==================== HELPERS INTERNOS ====================


def _get_densidad_base_org_m2(db: Session, ciclo_id: int, estanque_id: int) -> Optional[Decimal]:
    """
    Densidad base de siembra para un estanque.

    REGLA IMPORTANTE:
    - Si override > 0: usar override
    - Si override == 0 o None: usar plan
    - Solo retorna si hay siembra CONFIRMADA (status='f')
    """
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        return None

    se = (
        db.query(SiembraEstanque)
        .filter(
            SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
            SiembraEstanque.estanque_id == estanque_id,
            SiembraEstanque.status == "f"
        )
        .first()
    )

    if not se:
        return None

    if se.densidad_override_org_m2 is not None and se.densidad_override_org_m2 > 0:
        return Decimal(str(se.densidad_override_org_m2))

    if plan.densidad_org_m2 is not None and plan.densidad_org_m2 > 0:
        return Decimal(str(plan.densidad_org_m2))

    return None


def _get_densidad_retirada_acum(db: Session, ciclo_id: int, estanque_id: int) -> Decimal:
    """Densidad acumulada retirada por cosechas."""
    total = (
        db.query(func.coalesce(func.sum(CosechaEstanque.densidad_retirada_org_m2), 0))
        .join(CosechaOla, CosechaEstanque.cosecha_ola_id == CosechaOla.cosecha_ola_id)
        .filter(
            CosechaOla.ciclo_id == ciclo_id,
            CosechaEstanque.estanque_id == estanque_id,
            CosechaEstanque.status == "c"
        )
        .scalar()
    )
    return Decimal(str(total or 0))


def _get_best_projection(db: Session, ciclo_id: int) -> Optional[Proyeccion]:
    """
    Obtiene la mejor proyección disponible.

    Prioridad:
    1. Borrador de reforecast (más reciente)
    2. Proyección publicada (is_current=True)
    """
    return (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id)
        .order_by(
            desc(Proyeccion.status == 'b'),
            desc(Proyeccion.is_current),
            desc(Proyeccion.published_at),
            desc(Proyeccion.created_at)
        )
        .first()
    )


def _get_published_projection(db: Session, ciclo_id: int) -> Optional[Proyeccion]:
    """Obtiene la proyección publicada (plan original)."""
    return (
        db.query(Proyeccion)
        .filter(
            Proyeccion.ciclo_id == ciclo_id,
            Proyeccion.status == 'p',
            Proyeccion.is_current == True
        )
        .first()
    )


def _get_draft_projection(db: Session, ciclo_id: int) -> Optional[Proyeccion]:
    """Obtiene el borrador más reciente (reforecast)."""
    return (
        db.query(Proyeccion)
        .filter(
            Proyeccion.ciclo_id == ciclo_id,
            Proyeccion.status == 'b',
            Proyeccion.source_type == SourceType.REFORECAST
        )
        .order_by(desc(Proyeccion.created_at))
        .first()
    )


def _get_line_for_today(db: Session, proyeccion_id: int, hoy: date) -> Optional[ProyeccionLinea]:
    """Busca la línea de proyección más cercana a hoy."""
    all_lines = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    if not all_lines:
        return None

    best = all_lines[0]
    best_diff = abs((best.fecha_plan - hoy).days)

    for ln in all_lines[1:]:
        diff = abs((ln.fecha_plan - hoy).days)
        if diff < best_diff:
            best = ln
            best_diff = diff

    return best


def _get_current_sob_pct(db: Session, ciclo_id: int, estanque_id: int) -> tuple[Optional[Decimal], Optional[str]]:
    """
    SOB vigente con FUENTE.

    Prioridad:
    1. Último log operativo (más reciente)
    2. Proyección (borrador > publicado)
    3. 100% (default inicial)
    """
    last_log = (
        db.query(SOBCambioLog)
        .filter(
            SOBCambioLog.ciclo_id == ciclo_id,
            SOBCambioLog.estanque_id == estanque_id
        )
        .order_by(desc(SOBCambioLog.changed_at))
        .first()
    )
    if last_log:
        return Decimal(str(last_log.sob_nueva_pct)), "operativa_actual"

    proj = _get_best_projection(db, ciclo_id)
    if proj:
        line = _get_line_for_today(db, proj.proyeccion_id, today_mazatlan())
        if line:
            return Decimal(str(line.sob_pct_linea)), "proyeccion"

    return Decimal("100.00"), "default_inicial"


def _get_current_pp_g(db: Session, ciclo_id: int, estanque_id: int) -> tuple[
    Optional[Decimal], Optional[str], Optional[datetime]]:
    """
    PP vigente con FUENTE y TIMESTAMP.

    Prioridad:
    1. Última biometría (más reciente)
    2. Proyección (borrador > publicado)
    3. Talla inicial del plan
    """
    last_bio = (
        db.query(Biometria)
        .filter(
            Biometria.ciclo_id == ciclo_id,
            Biometria.estanque_id == estanque_id
        )
        .order_by(desc(Biometria.created_at))
        .first()
    )
    if last_bio:
        return Decimal(str(last_bio.pp_g)), "biometria", last_bio.created_at

    proj = _get_best_projection(db, ciclo_id)
    if proj:
        line = _get_line_for_today(db, proj.proyeccion_id, today_mazatlan())
        if line:
            return Decimal(str(line.pp_g)), "proyeccion", None

    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if plan and plan.talla_inicial_g:
        return Decimal(str(plan.talla_inicial_g)), "plan_inicial", None

    return None, None, None


def _build_pond_snapshot(
        db: Session,
        estanque: Estanque,
        ciclo_id: int
) -> Optional[Dict[str, Any]]:
    """Snapshot de métricas actuales de un estanque."""
    dens_base = _get_densidad_base_org_m2(db, ciclo_id, estanque.estanque_id)

    if dens_base is None:
        return None

    dens_retirada = _get_densidad_retirada_acum(db, ciclo_id, estanque.estanque_id)
    sob_pct, sob_fuente = _get_current_sob_pct(db, ciclo_id, estanque.estanque_id)
    pp_g, pp_fuente, pp_timestamp = _get_current_pp_g(db, ciclo_id, estanque.estanque_id)

    if sob_pct is None or pp_g is None:
        return None

    sup = Decimal(str(estanque.superficie_m2))
    dens_viva = calculate_densidad_viva(dens_base, dens_retirada, sob_pct)
    org_vivos = calculate_org_vivos(dens_viva, sup)
    biomasa = calculate_biomasa_kg(org_vivos, pp_g)

    return {
        "estanque_id": int(estanque.estanque_id),
        "nombre": estanque.nombre,
        "superficie_m2": float(sup),
        "densidad_base_org_m2": float(dens_base),
        "densidad_retirada_acum_org_m2": float(dens_retirada),
        "densidad_viva_org_m2": float(dens_viva),
        "sob_vigente_pct": float(sob_pct),
        "sob_fuente": sob_fuente,
        "pp_vigente_g": float(pp_g),
        "pp_fuente": pp_fuente,
        "pp_updated_at": pp_timestamp,
        "org_vivos_est": float(org_vivos),
        "biomasa_est_kg": float(biomasa)
    }


def _aggregate_kpis(pond_snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
    """KPIs agregados con sample sizes."""
    if not pond_snapshots:
        return {
            "biomasa_total_kg": 0.0,
            "densidad_promedio_org_m2": None,
            "sob_operativo_prom_pct": None,
            "pp_promedio_g": None,
            "sample_sizes": {
                "ponds_total": 0,
                "ponds_with_density": 0,
                "ponds_with_org_vivos": 0
            }
        }

    biomasa_total = float(calculate_total_biomass(pond_snapshots))
    densidad_prom = calculate_weighted_density(pond_snapshots)
    sob_prom = calculate_global_sob(pond_snapshots)
    pp_prom = calculate_weighted_pp(pond_snapshots)

    ponds_total = len(pond_snapshots)
    ponds_with_dens = sum(1 for p in pond_snapshots if p.get("densidad_viva_org_m2") is not None)
    ponds_with_org = sum(1 for p in pond_snapshots if p.get("org_vivos_est") is not None)

    return {
        "biomasa_total_kg": biomasa_total,
        "densidad_promedio_org_m2": float(densidad_prom) if densidad_prom else None,
        "sob_operativo_prom_pct": float(sob_prom) if sob_prom else None,
        "pp_promedio_g": float(pp_prom) if pp_prom else None,
        "sample_sizes": {
            "ponds_total": ponds_total,
            "ponds_with_density": ponds_with_dens,
            "ponds_with_org_vivos": ponds_with_org
        }
    }


# ==================== GRÁFICAS - DASHBOARD CICLO ====================

def get_growth_curve_data(db: Session, ciclo_id: int) -> List[Dict[str, Any]]:
    """
    Serie temporal comparando proyección publicada vs draft (reforecast).

    Retorna:
    - pp_proyectado_original_g: Proyección publicada (plan original)
    - pp_ajustado_g: Proyección draft (ajustada con reforecast)
    - tiene_datos_reales: Indica si esa semana tiene anclaje de biometría
    """
    published = _get_published_projection(db, ciclo_id)

    published_data = []
    if published:
        lineas = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == published.proyeccion_id)
            .order_by(asc(ProyeccionLinea.semana_idx))
            .all()
        )
        published_data = [
            {
                "semana": line.semana_idx,
                "pp_proyectado_original_g": float(line.pp_g),
                "fecha": line.fecha_plan
            }
            for line in lineas
        ]

    draft = _get_draft_projection(db, ciclo_id)

    draft_data = []
    if draft:
        lineas = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
            .order_by(asc(ProyeccionLinea.semana_idx))
            .all()
        )
        draft_data = [
            {
                "semana": line.semana_idx,
                "pp_ajustado_g": float(line.pp_g),
                "fecha": line.fecha_plan,
                "tiene_datos_reales": "obs_pp:" in (line.nota or "")
            }
            for line in lineas
        ]

    merged = {}

    for item in published_data:
        merged[item["semana"]] = item

    for item in draft_data:
        semana = item["semana"]
        if semana in merged:
            merged[semana]["pp_ajustado_g"] = item["pp_ajustado_g"]
            merged[semana]["tiene_datos_reales"] = item["tiene_datos_reales"]
        else:
            merged[semana] = {
                "semana": semana,
                "fecha": item["fecha"],
                "pp_ajustado_g": item["pp_ajustado_g"],
                "tiene_datos_reales": item["tiene_datos_reales"]
            }

    return sorted(merged.values(), key=lambda x: x["semana"])


def get_biomass_evolution_data(
        db: Session,
        ciclo_id: int,
        pond_snapshots: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Serie temporal de biomasa comparando proyección publicada vs borrador.

    Retorna:
    - biomasa_proyectada_original_kg: Biomasa del plan publicado
    - biomasa_ajustada_kg: Biomasa del borrador (reforecast)
    - tiene_datos_reales: Indica si esa semana tiene anclaje
    """
    published = _get_published_projection(db, ciclo_id)
    draft = _get_draft_projection(db, ciclo_id)

    def _calculate_biomass_for_projection(proyeccion: Optional[Proyeccion]) -> List[Dict[str, Any]]:
        if not proyeccion:
            return []

        lineas = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == proyeccion.proyeccion_id)
            .order_by(asc(ProyeccionLinea.semana_idx))
            .all()
        )

        if not lineas:
            return []

        retiros_confirmados: Dict[int, List[Tuple[date, Decimal]]] = {}
        for snap in pond_snapshots:
            estanque_id = snap["estanque_id"]

            cosechas = (
                db.query(CosechaEstanque.fecha_cosecha, CosechaEstanque.densidad_retirada_org_m2)
                .join(CosechaOla, CosechaEstanque.cosecha_ola_id == CosechaOla.cosecha_ola_id)
                .filter(
                    CosechaOla.ciclo_id == ciclo_id,
                    CosechaEstanque.estanque_id == estanque_id,
                    CosechaEstanque.status == 'c'
                )
                .all()
            )

            retiros_confirmados[estanque_id] = [
                (c.fecha_cosecha, Decimal(str(c.densidad_retirada_org_m2 or 0)))
                for c in cosechas if c.fecha_cosecha
            ]

        retiros_acum_por_estanque = {snap["estanque_id"]: Decimal("0") for snap in pond_snapshots}

        result = []
        for line in lineas:
            fechas_confirmadas = set()
            for est_id, retiros_list in retiros_confirmados.items():
                for fecha_ret, dens_ret in retiros_list:
                    if fecha_ret == line.fecha_plan:
                        fechas_confirmadas.add(fecha_ret)

            if line.fecha_plan not in fechas_confirmadas:
                if line.cosecha_flag and line.retiro_org_m2:
                    for est_id in retiros_acum_por_estanque.keys():
                        retiros_acum_por_estanque[est_id] += Decimal(str(line.retiro_org_m2))

            biomasa_semana = Decimal("0")

            for snap in pond_snapshots:
                estanque_id = snap["estanque_id"]
                superficie = Decimal(str(snap["superficie_m2"]))
                dens_base = Decimal(str(snap["densidad_base_org_m2"]))

                retiros_confirmados_acum = Decimal("0")
                for fecha_ret, dens_ret in retiros_confirmados.get(estanque_id, []):
                    if fecha_ret <= line.fecha_plan:
                        retiros_confirmados_acum += dens_ret

                if retiros_confirmados_acum > 0:
                    retiros_acum_por_estanque[estanque_id] = retiros_confirmados_acum

                sob_pct = Decimal(str(line.sob_pct_linea))
                dens_con_sob = dens_base * (sob_pct / Decimal("100"))

                retiros_acum = retiros_acum_por_estanque[estanque_id]
                dens_viva = dens_con_sob - retiros_acum
                if dens_viva < 0:
                    dens_viva = Decimal("0")

                org_vivos = dens_viva * superficie
                pp_g = Decimal(str(line.pp_g))
                biomasa_est = calculate_biomasa_kg(org_vivos, pp_g)
                biomasa_semana += biomasa_est

            result.append({
                "semana": line.semana_idx,
                "biomasa_kg": round(float(biomasa_semana), 1),
                "fecha": line.fecha_plan,
                "tiene_datos_reales": "obs_pp:" in (line.nota or "") if proyeccion.status == 'b' else False
            })

        return result

    published_data = _calculate_biomass_for_projection(published)
    draft_data = _calculate_biomass_for_projection(draft)

    merged = {}

    for item in published_data:
        merged[item["semana"]] = {
            "semana": item["semana"],
            "fecha": item["fecha"],
            "biomasa_proyectada_original_kg": item["biomasa_kg"]
        }

    for item in draft_data:
        semana = item["semana"]
        if semana in merged:
            merged[semana]["biomasa_ajustada_kg"] = item["biomasa_kg"]
            merged[semana]["tiene_datos_reales"] = item["tiene_datos_reales"]
        else:
            merged[semana] = {
                "semana": semana,
                "fecha": item["fecha"],
                "biomasa_ajustada_kg": item["biomasa_kg"],
                "tiene_datos_reales": item["tiene_datos_reales"]
            }

    return sorted(merged.values(), key=lambda x: x["semana"])


def get_density_evolution_data(db: Session, ciclo_id: int) -> List[Dict[str, Any]]:
    """
    Serie temporal de densidad comparando proyección publicada vs borrador.

    Retorna:
    - densidad_proyectada_original_org_m2: Densidad del plan publicado
    - densidad_ajustada_org_m2: Densidad del borrador (reforecast)
    - tiene_datos_reales: Indica si esa semana tiene anclaje
    """
    published = _get_published_projection(db, ciclo_id)
    draft = _get_draft_projection(db, ciclo_id)

    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    dens_inicial = float(plan.densidad_org_m2) if plan else 80.0

    cosechas_confirmadas = (
        db.query(
            CosechaOla.ventana_inicio,
            func.avg(CosechaEstanque.densidad_retirada_org_m2).label("retiro_promedio")
        )
        .join(CosechaEstanque, CosechaOla.cosecha_ola_id == CosechaEstanque.cosecha_ola_id)
        .filter(
            CosechaOla.ciclo_id == ciclo_id,
            CosechaEstanque.status == 'c'
        )
        .group_by(CosechaOla.ventana_inicio)
        .all()
    )

    retiros_confirmados_map = {c.ventana_inicio: float(c.retiro_promedio) for c in cosechas_confirmadas}

    def _calculate_density_for_projection(proyeccion: Optional[Proyeccion]) -> List[Dict[str, Any]]:
        if not proyeccion:
            return []

        lineas = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == proyeccion.proyeccion_id)
            .order_by(asc(ProyeccionLinea.semana_idx))
            .all()
        )

        result = []
        retiro_acumulado = 0.0

        for line in lineas:
            dens_viva = dens_inicial * (float(line.sob_pct_linea) / 100)

            if line.fecha_plan in retiros_confirmados_map:
                retiro_acumulado += retiros_confirmados_map[line.fecha_plan]
            elif line.cosecha_flag and line.retiro_org_m2:
                retiro_acumulado += float(line.retiro_org_m2)

            dens_viva -= retiro_acumulado
            if dens_viva < 0:
                dens_viva = 0

            result.append({
                "semana": line.semana_idx,
                "densidad_org_m2": round(dens_viva, 2),
                "fecha": line.fecha_plan,
                "tiene_datos_reales": "obs_pp:" in (line.nota or "") if proyeccion.status == 'b' else False
            })

        return result

    published_data = _calculate_density_for_projection(published)
    draft_data = _calculate_density_for_projection(draft)

    merged = {}

    for item in published_data:
        merged[item["semana"]] = {
            "semana": item["semana"],
            "fecha": item["fecha"],
            "densidad_proyectada_original_org_m2": item["densidad_org_m2"]
        }

    for item in draft_data:
        semana = item["semana"]
        if semana in merged:
            merged[semana]["densidad_ajustada_org_m2"] = item["densidad_org_m2"]
            merged[semana]["tiene_datos_reales"] = item["tiene_datos_reales"]
        else:
            merged[semana] = {
                "semana": semana,
                "fecha": item["fecha"],
                "densidad_ajustada_org_m2": item["densidad_org_m2"],
                "tiene_datos_reales": item["tiene_datos_reales"]
            }

    return sorted(merged.values(), key=lambda x: x["semana"])


def get_sob_evolution_data(db: Session, ciclo_id: int) -> List[Dict[str, Any]]:
    """
    Serie temporal de SOB comparando proyección publicada vs borrador.

    Retorna:
    - sob_proyectado_original_pct: SOB del plan publicado
    - sob_ajustado_pct: SOB del borrador (reforecast)
    - tiene_datos_reales: Indica si esa semana tiene anclaje
    """
    published = _get_published_projection(db, ciclo_id)
    draft = _get_draft_projection(db, ciclo_id)

    published_data = []
    if published:
        lineas = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == published.proyeccion_id)
            .order_by(asc(ProyeccionLinea.semana_idx))
            .all()
        )
        published_data = [
            {
                "semana": line.semana_idx,
                "sob_proyectado_original_pct": float(line.sob_pct_linea),
                "fecha": line.fecha_plan
            }
            for line in lineas
        ]

    draft_data = []
    if draft:
        lineas = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
            .order_by(asc(ProyeccionLinea.semana_idx))
            .all()
        )
        draft_data = [
            {
                "semana": line.semana_idx,
                "sob_ajustado_pct": float(line.sob_pct_linea),
                "fecha": line.fecha_plan,
                "tiene_datos_reales": "obs_pp:" in (line.nota or "")
            }
            for line in lineas
        ]

    merged = {}

    for item in published_data:
        merged[item["semana"]] = item

    for item in draft_data:
        semana = item["semana"]
        if semana in merged:
            merged[semana]["sob_ajustado_pct"] = item["sob_ajustado_pct"]
            merged[semana]["tiene_datos_reales"] = item["tiene_datos_reales"]
        else:
            merged[semana] = {
                "semana": semana,
                "fecha": item["fecha"],
                "sob_ajustado_pct": item["sob_ajustado_pct"],
                "tiene_datos_reales": item["tiene_datos_reales"]
            }

    return sorted(merged.values(), key=lambda x: x["semana"])


# ==================== GRÁFICAS - DASHBOARD ESTANQUE ====================

def _get_pond_growth_curve(db: Session, ciclo_id: int, estanque_id: int) -> List[Dict[str, Any]]:
    """
    Curva de crecimiento del estanque comparando:
    - Proyección general del ciclo (draft o published)
    - Biometrías reales del estanque específico
    """
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        return []

    siembra = (
        db.query(SiembraEstanque)
        .filter(
            SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
            SiembraEstanque.estanque_id == estanque_id,
            SiembraEstanque.status == "f"
        )
        .first()
    )

    if not siembra or not siembra.fecha_siembra:
        return []

    fecha_siembra = siembra.fecha_siembra

    proyeccion = _get_best_projection(db, ciclo_id)

    proyeccion_data = []
    if proyeccion:
        lineas = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == proyeccion.proyeccion_id)
            .order_by(asc(ProyeccionLinea.semana_idx))
            .all()
        )
        proyeccion_data = [
            {
                "semana": line.semana_idx,
                "pp_proyectado_g": float(line.pp_g),
                "fecha": line.fecha_plan
            }
            for line in lineas
        ]

    bios = (
        db.query(Biometria)
        .filter(
            Biometria.ciclo_id == ciclo_id,
            Biometria.estanque_id == estanque_id
        )
        .order_by(asc(Biometria.fecha))
        .all()
    )

    merged = {}

    for item in proyeccion_data:
        merged[item["semana"]] = item

    for bio in bios:
        fecha_bio = bio.fecha.date()
        pp_real = float(bio.pp_g)

        if not proyeccion_data:
            semana_calc = (fecha_bio - fecha_siembra).days // 7
            merged[semana_calc] = {
                "semana": semana_calc,
                "pp_real_g": pp_real,
                "fecha": fecha_bio
            }
            continue

        mejor_semana = proyeccion_data[0]["semana"]
        mejor_diff = abs((proyeccion_data[0]["fecha"] - fecha_bio).days)

        for item in proyeccion_data[1:]:
            diff = abs((item["fecha"] - fecha_bio).days)
            if diff < mejor_diff:
                mejor_diff = diff
                mejor_semana = item["semana"]

        if mejor_semana in merged:
            merged[mejor_semana]["pp_real_g"] = pp_real
        else:
            merged[mejor_semana] = {
                "semana": mejor_semana,
                "pp_real_g": pp_real,
                "fecha": fecha_bio
            }

    return sorted(merged.values(), key=lambda x: x["semana"])


def _get_pond_density_curve(db: Session, ciclo_id: int, estanque_id: int) -> List[Dict[str, Any]]:
    """
    Curva de densidad del estanque (decrece por cosechas).
    """
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        return []

    siembra = (
        db.query(SiembraEstanque)
        .filter(
            SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
            SiembraEstanque.estanque_id == estanque_id,
            SiembraEstanque.status == "f"
        )
        .first()
    )

    if not siembra or not siembra.fecha_siembra:
        return []

    fecha_siembra = siembra.fecha_siembra
    dens_base = _get_densidad_base_org_m2(db, ciclo_id, estanque_id)

    if not dens_base:
        return []

    cosechas = (
        db.query(CosechaEstanque)
        .join(CosechaOla, CosechaEstanque.cosecha_ola_id == CosechaOla.cosecha_ola_id)
        .filter(
            CosechaOla.ciclo_id == ciclo_id,
            CosechaEstanque.estanque_id == estanque_id,
            CosechaEstanque.status == 'c'
        )
        .order_by(asc(CosechaEstanque.fecha_cosecha))
        .all()
    )

    curve = []
    dens_actual = float(dens_base)

    curve.append({
        "semana": 0,
        "densidad_org_m2": dens_actual,
        "fecha": fecha_siembra
    })

    for cosecha in cosechas:
        if cosecha.densidad_retirada_org_m2:
            dens_actual -= float(cosecha.densidad_retirada_org_m2)
            dens_actual = max(0, dens_actual)
            semana = (cosecha.fecha_cosecha - fecha_siembra).days // 7

            curve.append({
                "semana": semana,
                "densidad_org_m2": round(dens_actual, 2),
                "fecha": cosecha.fecha_cosecha
            })

    return sorted(curve, key=lambda x: x["semana"])


# ==================== RESTO DE FUNCIONES ====================

def _get_cycle_estados(db: Session, ciclo_id: int) -> Dict[str, int]:
    """Estados de estanques en el ciclo."""
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()

    if not plan:
        return {"activos": 0, "en_siembra": 0, "en_cosecha": 0, "finalizados": 0}

    siembras = (
        db.query(SiembraEstanque)
        .filter(SiembraEstanque.siembra_plan_id == plan.siembra_plan_id)
        .all()
    )

    en_siembra = sum(1 for s in siembras if s.status == 'p')
    sembrados = [s for s in siembras if s.status == 'f']

    finalizados = 0
    en_cosecha_parcial = 0

    for siembra in sembrados:
        cosecha_final = (
            db.query(CosechaEstanque)
            .join(CosechaOla, CosechaEstanque.cosecha_ola_id == CosechaOla.cosecha_ola_id)
            .filter(
                CosechaOla.ciclo_id == ciclo_id,
                CosechaEstanque.estanque_id == siembra.estanque_id,
                CosechaOla.tipo == 'f',
                CosechaEstanque.status == 'c'
            )
            .first()
        )

        if cosecha_final:
            finalizados += 1
        else:
            cosecha_parcial = (
                db.query(CosechaEstanque)
                .join(CosechaOla, CosechaEstanque.cosecha_ola_id == CosechaOla.cosecha_ola_id)
                .filter(
                    CosechaOla.ciclo_id == ciclo_id,
                    CosechaEstanque.estanque_id == siembra.estanque_id,
                    CosechaOla.tipo == 'p',
                    CosechaEstanque.status == 'c'
                )
                .first()
            )

            if cosecha_parcial:
                en_cosecha_parcial += 1

    activos = len(sembrados) - finalizados - en_cosecha_parcial

    return {
        "activos": activos,
        "en_siembra": en_siembra,
        "en_cosecha": en_cosecha_parcial,
        "finalizados": finalizados
    }


def _calculate_pond_growth_rate(db: Session, ciclo_id: int, estanque_id: int) -> Optional[float]:
    """Tasa de crecimiento del estanque (g/semana)."""
    bios = (
        db.query(Biometria)
        .filter(
            Biometria.ciclo_id == ciclo_id,
            Biometria.estanque_id == estanque_id
        )
        .order_by(asc(Biometria.fecha))
        .all()
    )

    if len(bios) < 2:
        return None

    first = bios[0]
    last = bios[-1]

    dias = (last.fecha - first.fecha).days
    if dias <= 0:
        return None

    rate = calculate_growth_rate(
        Decimal(str(last.pp_g)),
        Decimal(str(first.pp_g)),
        dias
    )

    return float(rate) if rate else None


# ==================== FUNCIONES PRINCIPALES ====================

def get_cycle_overview(
        db: Session,
        ciclo_id: int
) -> Dict[str, Any]:
    """Dashboard general del ciclo."""
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise ValueError("Ciclo no encontrado")

    estanques = db.query(Estanque).filter(Estanque.granja_id == ciclo.granja_id).all()

    pond_snapshots = []
    for est in estanques:
        snap = _build_pond_snapshot(db, est, ciclo_id)
        if snap:
            pond_snapshots.append(snap)

    dias_ciclo = (today_mazatlan() - ciclo.fecha_inicio).days
    kpis = _aggregate_kpis(pond_snapshots)

    estados = _get_cycle_estados(db, ciclo_id)

    growth_curve = get_growth_curve_data(db, ciclo_id)
    biomass_evolution = get_biomass_evolution_data(db, ciclo_id, pond_snapshots)
    density_evolution = get_density_evolution_data(db, ciclo_id)
    sob_evolution = get_sob_evolution_data(db, ciclo_id)

    proximas_siembras = _get_upcoming_siembras(db, ciclo_id)
    proximas_cosechas = _get_upcoming_cosechas(db, ciclo_id, days_ahead=90)

    return {
        "ciclo_id": ciclo_id,
        "nombre": ciclo.nombre,
        "fecha_inicio": ciclo.fecha_inicio,
        "kpis": {
            "dias_ciclo": dias_ciclo,
            **kpis,
            "estados": estados
        },
        "graficas": {
            "crecimiento": growth_curve,
            "biomasa_evolucion": biomass_evolution,
            "densidad_evolucion": density_evolution,
            "sob_evolucion": sob_evolution
        },
        "proximas_siembras": proximas_siembras,
        "proximas_cosechas": proximas_cosechas,
        "por_estanque": pond_snapshots
    }


def get_pond_detail(
        db: Session,
        estanque_id: int,
        ciclo_id: int
) -> Dict[str, Any]:
    """Dashboard detallado de un estanque."""
    estanque = db.get(Estanque, estanque_id)
    if not estanque:
        raise ValueError("Estanque no encontrado")

    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise ValueError("Ciclo no encontrado")

    snapshot = _build_pond_snapshot(db, estanque, ciclo_id)
    if not snapshot:
        raise ValueError("No hay datos suficientes para este estanque en el ciclo")

    dens_base = _get_densidad_base_org_m2(db, ciclo_id, estanque_id)

    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    siembra = None
    if plan:
        siembra = (
            db.query(SiembraEstanque)
            .filter(
                SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
                SiembraEstanque.estanque_id == estanque_id,
                SiembraEstanque.status == "f"
            )
            .first()
        )

    if siembra and siembra.fecha_siembra:
        dias_cultivo = (today_mazatlan() - siembra.fecha_siembra).days
    else:
        dias_cultivo = 0

    biomasa_m2 = snapshot["biomasa_est_kg"] / snapshot["superficie_m2"]

    growth_rate = _calculate_pond_growth_rate(db, ciclo_id, estanque_id)

    growth_curve = _get_pond_growth_curve(db, ciclo_id, estanque_id)
    density_curve = _get_pond_density_curve(db, ciclo_id, estanque_id)

    return {
        "estanque_id": estanque_id,
        "nombre": estanque.nombre,
        "status": estanque.status,
        "kpis": {
            "biomasa_estimada_kg": snapshot["biomasa_est_kg"],
            "densidad_actual_org_m2": snapshot["densidad_viva_org_m2"],
            "org_vivos": snapshot["org_vivos_est"],
            "pp_g": snapshot["pp_vigente_g"],
            "pp_fuente": snapshot["pp_fuente"],
            "pp_updated_at": snapshot["pp_updated_at"],
            "supervivencia_pct": snapshot["sob_vigente_pct"],
            "sob_fuente": snapshot["sob_fuente"]
        },
        "graficas": {
            "crecimiento": growth_curve,
            "densidad_evolucion": density_curve
        },
        "detalles": {
            "superficie_m2": snapshot["superficie_m2"],
            "densidad_inicial_org_m2": float(dens_base) if dens_base else None,
            "dias_cultivo": dias_cultivo,
            "tasa_crecimiento_g_sem": growth_rate,
            "biomasa_m2": round(biomasa_m2, 2)
        }
    }


def _get_upcoming_siembras(db: Session, ciclo_id: int) -> List[Dict[str, Any]]:
    """Siembras pendientes del ciclo."""
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        return []

    siembras = (
        db.query(SiembraEstanque, Estanque.nombre)
        .join(Estanque, SiembraEstanque.estanque_id == Estanque.estanque_id)
        .filter(
            SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
            SiembraEstanque.status == "p"
        )
        .order_by(asc(SiembraEstanque.fecha_tentativa))
        .all()
    )

    result = []
    today = today_mazatlan()
    for s in siembras:
        dias_diff = (s.SiembraEstanque.fecha_tentativa - today).days

        if dias_diff < 0:
            estado = "atrasada"
        elif dias_diff <= 7:
            estado = "proxima"
        else:
            estado = "futura"

        result.append({
            "estanque_id": s.SiembraEstanque.estanque_id,
            "estanque_nombre": s.nombre,
            "fecha_tentativa": s.SiembraEstanque.fecha_tentativa,
            "dias_diferencia": dias_diff,
            "estado": estado
        })

    return result


def _get_upcoming_cosechas(db: Session, ciclo_id: int, days_ahead: int = 90) -> List[Dict[str, Any]]:
    """Cosechas pendientes del ciclo."""
    today = today_mazatlan()
    horizon = today + timedelta(days=days_ahead)

    olas = (
        db.query(CosechaOla)
        .filter(
            CosechaOla.ciclo_id == ciclo_id,
            CosechaOla.ventana_inicio <= horizon
        )
        .order_by(asc(CosechaOla.ventana_inicio))
        .all()
    )

    result = []
    for ola in olas:
        estanques_pendientes = (
            db.query(func.count(CosechaEstanque.cosecha_estanque_id))
            .filter(
                CosechaEstanque.cosecha_ola_id == ola.cosecha_ola_id,
                CosechaEstanque.status == 'p'
            )
            .scalar()
        )

        if estanques_pendientes == 0:
            continue

        dias_diff = (ola.ventana_inicio - today).days

        if dias_diff < 0:
            estado = "atrasada"
        elif dias_diff <= 7:
            estado = "proxima"
        else:
            estado = "futura"

        result.append({
            "cosecha_ola_id": ola.cosecha_ola_id,
            "tipo": ola.tipo,
            "ventana_inicio": ola.ventana_inicio,
            "ventana_fin": ola.ventana_fin,
            "estanques_pendientes": estanques_pendientes,
            "dias_diferencia": dias_diff,
            "estado": estado
        })

    return result