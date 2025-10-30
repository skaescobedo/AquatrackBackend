"""
Servicio de analytics para preparar datos de dashboards.
Consumido por api/analytics_routes.py

MEJORAS vs versión anterior:
- Filtrado estricto: solo estanques con siembra confirmada
- Fuentes de datos (pp_fuente, sob_fuente, pp_updated_at)
- SOB global correcto (reconstruye remanente pre-SOB)
- PP promedio robusto (mini-fix para nulls)
- Sample sizes (metadata de cuántos estanques contribuyen)
- Solo usa proyecciones publicadas (is_current=True)
"""
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc

from models.cycle import Ciclo
from models.pond import Estanque
from models.biometria import Biometria, SOBCambioLog
from models.projection import Proyeccion, ProyeccionLinea
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

from utils.permissions import ensure_user_in_farm_or_admin


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
            SiembraEstanque.status == "f"  # ← CAMBIO: Solo confirmadas
        )
        .first()
    )

    # Si no hay siembra confirmada, retornar None
    if not se:
        return None

    # Prioridad: override (si >0) > plan
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


def _get_current_projection(db: Session, ciclo_id: int) -> Optional[Proyeccion]:
    """
    Obtiene la proyección ACTUAL (is_current=True).

    CAMBIO: Solo usa proyecciones publicadas, NO borradores.
    """
    return (
        db.query(Proyeccion)
        .filter(
            Proyeccion.ciclo_id == ciclo_id,
            Proyeccion.is_current == True,
            Proyeccion.status == "p"  # ← Solo publicadas
        )
        .first()
    )


def _get_line_for_today(db: Session, proyeccion_id: int, today: date) -> Optional[ProyeccionLinea]:
    """
    Línea de proyección más cercana a 'today'.
    Prioriza pasado sobre futuro si están a la misma distancia.
    """
    prev_line = (
        db.query(ProyeccionLinea)
        .filter(
            ProyeccionLinea.proyeccion_id == proyeccion_id,
            ProyeccionLinea.fecha_plan <= today
        )
        .order_by(desc(ProyeccionLinea.fecha_plan))
        .first()
    )

    next_line = (
        db.query(ProyeccionLinea)
        .filter(
            ProyeccionLinea.proyeccion_id == proyeccion_id,
            ProyeccionLinea.fecha_plan >= today
        )
        .order_by(asc(ProyeccionLinea.fecha_plan))
        .first()
    )

    if prev_line and next_line:
        diff_prev = abs((today - prev_line.fecha_plan).days)
        diff_next = abs((next_line.fecha_plan - today).days)
        return prev_line if diff_prev <= diff_next else next_line

    return prev_line or next_line


def _get_current_sob_pct(db: Session, ciclo_id: int, estanque_id: int) -> tuple[Optional[Decimal], Optional[str]]:
    """
    SOB vigente con FUENTE.

    Prioridad:
    1. Último log operativo (más reciente)
    2. Proyección actual (línea cercana a hoy)
    3. 100% (default inicial)

    Returns: (sob_pct, fuente)
    """
    # 1) Último log operativo
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

    # 2) Proyección actual
    proj = _get_current_projection(db, ciclo_id)
    if proj:
        line = _get_line_for_today(db, proj.proyeccion_id, date.today())
        if line:
            return Decimal(str(line.sob_pct_linea)), "proyeccion"

    # 3) Default inicial
    return Decimal("100.00"), "default_inicial"


def _get_current_pp_g(db: Session, ciclo_id: int, estanque_id: int) -> tuple[Optional[Decimal], Optional[str], Optional[datetime]]:
    """
    PP vigente con FUENTE y TIMESTAMP.

    Prioridad:
    1. Última biometría (más reciente)
    2. Proyección actual (línea cercana a hoy)
    3. Talla inicial del plan (0.015g típicamente)

    Returns: (pp_g, fuente, timestamp)
    """
    # 1) Última biometría
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

    # 2) Proyección actual
    proj = _get_current_projection(db, ciclo_id)
    if proj:
        line = _get_line_for_today(db, proj.proyeccion_id, date.today())
        if line:
            return Decimal(str(line.pp_g)), "proyeccion", None

    # 3) Talla inicial del plan
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if plan and plan.talla_inicial_g:
        return Decimal(str(plan.talla_inicial_g)), "plan_inicial", None

    return None, None, None


def _build_pond_snapshot(
    db: Session,
    estanque: Estanque,
    ciclo_id: int
) -> Optional[Dict[str, Any]]:
    """
    Snapshot de métricas actuales de un estanque.

    MEJORAS:
    - Solo incluye si hay siembra confirmada
    - Retorna fuentes de datos
    - Incluye timestamp de última actualización
    """
    dens_base = _get_densidad_base_org_m2(db, ciclo_id, estanque.estanque_id)

    # CAMBIO: Si no hay siembra confirmada, no incluir
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
        "sob_fuente": sob_fuente,  # ← NUEVO
        "pp_vigente_g": float(pp_g),
        "pp_fuente": pp_fuente,  # ← NUEVO
        "pp_updated_at": pp_timestamp,  # ← NUEVO
        "org_vivos_est": float(org_vivos),
        "biomasa_est_kg": float(biomasa)
    }


def _aggregate_kpis(pond_snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    KPIs agregados con sample sizes.

    MEJORAS:
    - Usa calculate_global_sob mejorado
    - Usa calculate_weighted_pp con mini-fix
    - Retorna metadata (sample_sizes)
    """
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

    # Sample sizes
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


# ==================== FUNCIONES PRINCIPALES ====================

def get_cycle_overview(
    db: Session,
    user_id: int,
    is_admin: bool,
    ciclo_id: int
) -> Dict[str, Any]:
    """
    Dashboard general del ciclo.

    MEJORAS:
    - Solo estanques con siembra confirmada
    - Retorna fuentes de datos
    - Sample sizes en KPIs
    """
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise ValueError("Ciclo no encontrado")

    ensure_user_in_farm_or_admin(db, user_id, ciclo.granja_id, is_admin)

    # Estanques de la granja
    estanques = db.query(Estanque).filter(Estanque.granja_id == ciclo.granja_id).all()

    # Snapshots actuales (solo con siembra confirmada)
    pond_snapshots = []
    for est in estanques:
        snap = _build_pond_snapshot(db, est, ciclo_id)
        if snap:
            pond_snapshots.append(snap)

    # KPIs agregados
    dias_ciclo = (date.today() - ciclo.fecha_inicio).days
    kpis = _aggregate_kpis(pond_snapshots)

    # Estados (placeholder)
    estados = _get_cycle_estados(db, ciclo_id)

    # Gráficas
    growth_curve = get_growth_curve_data(db, ciclo_id)
    biomass_evolution = get_biomass_evolution_data(db, ciclo_id, pond_snapshots)
    density_evolution = get_density_evolution_data(db, ciclo_id)

    # Próximas operaciones
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
            "densidad_evolucion": density_evolution
        },
        "proximas_siembras": proximas_siembras,
        "proximas_cosechas": proximas_cosechas,
        "por_estanque": pond_snapshots  # ← NUEVO: Detalle por estanque
    }


def get_pond_detail(
    db: Session,
    user_id: int,
    is_admin: bool,
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

    ensure_user_in_farm_or_admin(db, user_id, estanque.granja_id, is_admin)

    # Snapshot actual
    snapshot = _build_pond_snapshot(db, estanque, ciclo_id)
    if not snapshot:
        raise ValueError("No hay datos suficientes para este estanque en el ciclo")

    # Densidad inicial
    dens_base = _get_densidad_base_org_m2(db, ciclo_id, estanque_id)

    # Días de cultivo
    dias_cultivo = (date.today() - ciclo.fecha_inicio).days

    # Rendimiento (biomasa/superficie)
    biomasa_m2 = snapshot["biomasa_est_kg"] / snapshot["superficie_m2"]

    # Tasa de crecimiento
    growth_rate = _calculate_pond_growth_rate(db, ciclo_id, estanque_id)

    # Gráficas
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
            "pp_fuente": snapshot["pp_fuente"],  # ← NUEVO
            "pp_updated_at": snapshot["pp_updated_at"],  # ← NUEVO
            "supervivencia_pct": snapshot["sob_vigente_pct"],
            "sob_fuente": snapshot["sob_fuente"]  # ← NUEVO
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


# ==================== GRÁFICAS ====================

def get_growth_curve_data(db: Session, ciclo_id: int) -> List[Dict[str, Any]]:
    """Serie temporal de PP promedio del ciclo."""
    # Proyección
    proj = _get_current_projection(db, ciclo_id)
    proyeccion_data = []
    if proj:
        lineas = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == proj.proyeccion_id)
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

    # Real (biometrías)
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        return proyeccion_data

    biometrias = (
        db.query(
            Biometria.fecha,
            func.avg(Biometria.pp_g).label("pp_prom")
        )
        .filter(Biometria.ciclo_id == ciclo_id)
        .group_by(Biometria.fecha)
        .order_by(asc(Biometria.fecha))
        .all()
    )

    real_data = []
    for bio in biometrias:
        dias = (bio.fecha.date() - ciclo.fecha_inicio).days
        semana = dias // 7
        real_data.append({
            "semana": semana,
            "pp_real_g": float(bio.pp_prom),
            "fecha": bio.fecha.date()
        })

    # Merge
    merged = {}
    for item in proyeccion_data:
        merged[item["semana"]] = item

    for item in real_data:
        if item["semana"] in merged:
            merged[item["semana"]]["pp_real_g"] = item["pp_real_g"]
        else:
            merged[item["semana"]] = item

    return sorted(merged.values(), key=lambda x: x["semana"])


def get_biomass_evolution_data(
    db: Session,
    ciclo_id: int,
    pond_snapshots: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Serie temporal de biomasa acumulada."""
    proj = _get_current_projection(db, ciclo_id)
    if not proj:
        return []

    lineas = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == proj.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    biomasa_actual = sum(p["biomasa_est_kg"] for p in pond_snapshots)

    result = []
    for line in lineas:
        proporcion = line.semana_idx / max(lineas[-1].semana_idx, 1)
        biomasa_est = biomasa_actual * proporcion

        result.append({
            "semana": line.semana_idx,
            "biomasa_kg": round(biomasa_est, 1),
            "fecha": line.fecha_plan
        })

    return result


def get_density_evolution_data(db: Session, ciclo_id: int) -> List[Dict[str, Any]]:
    """Serie temporal de densidad promedio."""
    proj = _get_current_projection(db, ciclo_id)
    if not proj:
        return []

    lineas = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == proj.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    dens_inicial = float(plan.densidad_org_m2) if plan else 80.0

    result = []
    for line in lineas:
        dens_viva = dens_inicial * (float(line.sob_pct_linea) / 100)

        if line.cosecha_flag and line.retiro_org_m2:
            dens_viva -= float(line.retiro_org_m2)

        result.append({
            "semana": line.semana_idx,
            "densidad_org_m2": round(dens_viva, 2),
            "fecha": line.fecha_plan
        })

    return result


# ==================== OPERACIONES PRÓXIMAS ====================

def _get_upcoming_siembras(db: Session, ciclo_id: int) -> List[Dict[str, Any]]:
    """Siembras pendientes del ciclo (todas)."""
    today = date.today()

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
    today = date.today()

    olas = (
        db.query(CosechaOla)
        .filter(
            CosechaOla.ciclo_id == ciclo_id,
            CosechaOla.status == "p"
        )
        .order_by(asc(CosechaOla.ventana_inicio))
        .all()
    )

    result = []
    for ola in olas:
        dias_hasta = (ola.ventana_inicio - today).days

        if dias_hasta < 0:
            estado = "atrasada"
        elif dias_hasta <= 7:
            estado = "urgente"
        elif dias_hasta <= days_ahead:
            estado = "pendiente"
        else:
            estado = "futura"

        pendientes = (
            db.query(func.count(CosechaEstanque.cosecha_estanque_id))
            .filter(
                CosechaEstanque.cosecha_ola_id == ola.cosecha_ola_id,
                CosechaEstanque.status == "p"
            )
            .scalar()
        ) or 0

        result.append({
            "ola_id": ola.cosecha_ola_id,
            "nombre": ola.nombre,
            "tipo": "Parcial" if ola.tipo == "p" else "Final",
            "ventana_inicio": ola.ventana_inicio,
            "ventana_fin": ola.ventana_fin,
            "dias_hasta_inicio": dias_hasta,
            "estado": estado,
            "estanques_pendientes": pendientes
        })

    return result


def _get_cycle_estados(db: Session, ciclo_id: int) -> Dict[str, int]:
    """Estados del ciclo (placeholder)."""
    return {
        "activos": 3,
        "en_siembra": 1,
        "en_cosecha": 0,
        "finalizados": 0
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


def _get_pond_growth_curve(db: Session, ciclo_id: int, estanque_id: int) -> List[Dict[str, Any]]:
    """Curva de crecimiento del estanque."""
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        return []

    bios = (
        db.query(Biometria)
        .filter(
            Biometria.ciclo_id == ciclo_id,
            Biometria.estanque_id == estanque_id
        )
        .order_by(asc(Biometria.fecha))
        .all()
    )

    return [
        {
            "semana": (bio.fecha.date() - ciclo.fecha_inicio).days // 7,
            "pp_g": float(bio.pp_g),
            "fecha": bio.fecha.date()
        }
        for bio in bios
    ]


def _get_pond_density_curve(db: Session, ciclo_id: int, estanque_id: int) -> List[Dict[str, Any]]:
    """Curva de densidad del estanque."""
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        return []

    dens_base = _get_densidad_base_org_m2(db, ciclo_id, estanque_id)
    if not dens_base:
        return []

    cosechas = (
        db.query(CosechaEstanque)
        .join(CosechaOla, CosechaEstanque.cosecha_ola_id == CosechaOla.cosecha_ola_id)
        .filter(
            CosechaOla.ciclo_id == ciclo_id,
            CosechaEstanque.estanque_id == estanque_id,
            CosechaEstanque.status == "c"
        )
        .order_by(asc(CosechaEstanque.fecha_cosecha))
        .all()
    )

    result = []
    dens_actual = float(dens_base)

    result.append({
        "semana": 0,
        "densidad_org_m2": dens_actual,
        "fecha": ciclo.fecha_inicio
    })

    for cosecha in cosechas:
        if cosecha.densidad_retirada_org_m2:
            dens_actual -= float(cosecha.densidad_retirada_org_m2)
            semana = (cosecha.fecha_cosecha - ciclo.fecha_inicio).days // 7
            result.append({
                "semana": semana,
                "densidad_org_m2": round(dens_actual, 2),
                "fecha": cosecha.fecha_cosecha
            })

    return result