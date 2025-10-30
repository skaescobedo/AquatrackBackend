"""
Servicio de analytics para preparar datos de dashboards.
Consumido por api/analytics_routes.py
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
from services.projection_service import get_current_projection

from utils.permissions import ensure_user_in_farm_or_admin


# ==================== HELPERS INTERNOS ====================


def _get_densidad_base_org_m2(db: Session, ciclo_id: int, estanque_id: int) -> Optional[Decimal]:
    """Densidad base de siembra para un estanque."""
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
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
        ov = Decimal(str(se.densidad_override_org_m2))
        if ov > 0:
            return ov

    if plan.densidad_org_m2 is not None:
        pv = Decimal(str(plan.densidad_org_m2))
        if pv > 0:
            return pv

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


def _get_current_sob_pct(db: Session, ciclo_id: int, estanque_id: int) -> Optional[Decimal]:
    """SOB vigente: último log operativo o proyección."""
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
        return Decimal(str(last_log.sob_nueva_pct))

    # 2) Proyección actual
    proj = get_current_projection(db, ciclo_id)
    if proj:
        # Línea más reciente con sob
        line = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == proj.proyeccion_id)
            .order_by(desc(ProyeccionLinea.fecha_plan))
            .first()
        )
        if line:
            return Decimal(str(line.sob_pct_linea))

    return None


def _get_current_pp_g(db: Session, ciclo_id: int, estanque_id: int) -> Optional[Decimal]:
    """PP vigente: última biometría o proyección."""
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
        return Decimal(str(last_bio.pp_g))

    # 2) Proyección actual
    proj = get_current_projection(db, ciclo_id)
    if proj:
        line = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == proj.proyeccion_id)
            .order_by(desc(ProyeccionLinea.fecha_plan))
            .first()
        )
        if line:
            return Decimal(str(line.pp_g))

    return None


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
    sob_pct = _get_current_sob_pct(db, ciclo_id, estanque.estanque_id)
    pp_g = _get_current_pp_g(db, ciclo_id, estanque.estanque_id)

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
        "densidad_viva_org_m2": float(dens_viva),
        "sob_vigente_pct": float(sob_pct),
        "pp_vigente_g": float(pp_g),
        "org_vivos_est": float(org_vivos),
        "biomasa_est_kg": float(biomasa)
    }


# ==================== FUNCIONES PRINCIPALES ====================

def get_cycle_overview(
    db: Session,
    user_id: int,
    is_admin: bool,
    ciclo_id: int
) -> Dict[str, Any]:
    """
    Dashboard general del ciclo (Imagen 1).

    Returns:
        - kpis: días, biomasa total, densidad promedio, 4 estados, SOB, PP
        - graficas: growth_curve, biomass_evolution, density_evolution
        - listas: proximas_siembras, proximas_cosechas
    """
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise ValueError("Ciclo no encontrado")

    ensure_user_in_farm_or_admin(db, user_id, ciclo.granja_id, is_admin)

    # Estanques de la granja
    estanques = db.query(Estanque).filter(Estanque.granja_id == ciclo.granja_id).all()

    # Snapshots actuales
    pond_snapshots = []
    for est in estanques:
        snap = _build_pond_snapshot(db, est, ciclo_id)
        if snap:
            pond_snapshots.append(snap)

    # KPIs agregados
    dias_ciclo = (date.today() - ciclo.fecha_inicio).days
    biomasa_total = float(calculate_total_biomass(pond_snapshots))
    densidad_prom = calculate_weighted_density(pond_snapshots)
    sob_prom = calculate_global_sob(pond_snapshots)
    pp_prom = calculate_weighted_pp(pond_snapshots)

    # Estados (placeholder - necesitas lógica de negocio específica)
    estados = _get_cycle_estados(db, ciclo_id)

    # Gráficas
    growth_curve = get_growth_curve_data(db, ciclo_id)
    biomass_evolution = get_biomass_evolution_data(db, ciclo_id, pond_snapshots)
    density_evolution = get_density_evolution_data(db, ciclo_id)

    # Próximas operaciones
    proximas_siembras = _get_upcoming_siembras(db, ciclo_id, days_ahead=7)
    proximas_cosechas = _get_upcoming_cosechas(db, ciclo_id, days_ahead=7)

    return {
        "ciclo_id": ciclo_id,
        "nombre": ciclo.nombre,
        "fecha_inicio": ciclo.fecha_inicio,
        "kpis": {
            "dias_ciclo": dias_ciclo,
            "biomasa_total_kg": biomasa_total,
            "densidad_promedio_org_m2": float(densidad_prom) if densidad_prom else None,
            "estados": estados,
            "sob_operativo_prom_pct": float(sob_prom) if sob_prom else None,
            "pp_promedio_g": float(pp_prom) if pp_prom else None
        },
        "graficas": {
            "crecimiento": growth_curve,
            "biomasa_evolucion": biomass_evolution,
            "densidad_evolucion": density_evolution
        },
        "proximas_siembras": proximas_siembras,
        "proximas_cosechas": proximas_cosechas
    }


def get_pond_detail(
    db: Session,
    user_id: int,
    is_admin: bool,
    estanque_id: int,
    ciclo_id: int
) -> Dict[str, Any]:
    """
    Dashboard detallado de un estanque (Imagen 2).

    Returns:
        - kpis: biomasa, densidad, org_vivos, pp, supervivencia
        - graficas: growth_curve, density_evolution
        - detalles: estado, superficie, densidad_inicial, dias_cultivo, rendimiento
    """
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

    # Supervivencia
    dens_retirada = _get_densidad_retirada_acum(db, ciclo_id, estanque_id)
    dens_rem = dens_base - dens_retirada if dens_base else None
    sob_pct = snapshot["sob_vigente_pct"]

    supervivencia = sob_pct  # Ya es el % de supervivencia actual

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
            "supervivencia_pct": supervivencia
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


def get_growth_curve_data(db: Session, ciclo_id: int) -> List[Dict[str, Any]]:
    """
    Serie temporal de PP promedio del ciclo.
    Para graficar: eje X = semana, eje Y = PP (real vs proyectado)
    """
    # 1) Proyección
    proj = get_current_projection(db, ciclo_id)
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

    # 2) Real (biometrías agrupadas por semana)
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

    # Merge proyección + real
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
    """
    Serie temporal de biomasa acumulada.
    Para graficar: eje X = semana, eje Y = biomasa total (kg)
    """
    proj = get_current_projection(db, ciclo_id)
    if not proj:
        return []

    lineas = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == proj.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    # Biomasa proyectada acumulada (simplificado)
    # En realidad necesitarías calcular org_vivos × pp por cada línea
    # Aquí asumimos biomasa actual como punto final
    biomasa_actual = sum(p["biomasa_est_kg"] for p in pond_snapshots)

    result = []
    for line in lineas:
        # Proporción lineal (placeholder - mejora con lógica real)
        proporcion = line.semana_idx / max(lineas[-1].semana_idx, 1)
        biomasa_est = biomasa_actual * proporcion

        result.append({
            "semana": line.semana_idx,
            "biomasa_kg": round(biomasa_est, 1),
            "fecha": line.fecha_plan
        })

    return result


def get_density_evolution_data(db: Session, ciclo_id: int) -> List[Dict[str, Any]]:
    """
    Serie temporal de densidad promedio.
    Decrece conforme hay cosechas parciales.
    """
    proj = get_current_projection(db, ciclo_id)
    if not proj:
        return []

    lineas = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == proj.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    # Densidad base
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    dens_inicial = float(plan.densidad_org_m2) if plan else 80.0

    result = []
    for line in lineas:
        # Densidad viva = densidad_base × SOB% - retiros acumulados
        # Simplificación: decrece por SOB y cosechas
        dens_viva = dens_inicial * (float(line.sob_pct_linea) / 100)

        if line.cosecha_flag and line.retiro_org_m2:
            dens_viva -= float(line.retiro_org_m2)

        result.append({
            "semana": line.semana_idx,
            "densidad_org_m2": round(dens_viva, 2),
            "fecha": line.fecha_plan
        })

    return result


# ==================== HELPERS DE OPERACIONES PRÓXIMAS ====================

def _get_upcoming_siembras(db: Session, ciclo_id: int, days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Siembras planeadas en los próximos N días."""
    today = date.today()
    horizon = today + timedelta(days=days_ahead)

    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        return []

    siembras = (
        db.query(SiembraEstanque, Estanque.nombre)
        .join(Estanque, SiembraEstanque.estanque_id == Estanque.estanque_id)
        .filter(
            SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
            SiembraEstanque.status == "p",
            SiembraEstanque.fecha_tentativa >= today,
            SiembraEstanque.fecha_tentativa <= horizon
        )
        .order_by(asc(SiembraEstanque.fecha_tentativa))
        .all()
    )

    return [
        {
            "estanque_id": s.SiembraEstanque.estanque_id,
            "estanque_nombre": s.nombre,
            "fecha_tentativa": s.SiembraEstanque.fecha_tentativa
        }
        for s in siembras
    ]


def _get_upcoming_cosechas(db: Session, ciclo_id: int, days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Cosechas planeadas en los próximos N días."""
    today = date.today()
    horizon = today + timedelta(days=days_ahead)

    olas = (
        db.query(CosechaOla)
        .filter(
            CosechaOla.ciclo_id == ciclo_id,
            CosechaOla.ventana_inicio <= horizon,
            CosechaOla.ventana_fin >= today
        )
        .order_by(asc(CosechaOla.ventana_inicio))
        .all()
    )

    result = []
    for ola in olas:
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
            "estanques_pendientes": pendientes
        })

    return result


def _get_cycle_estados(db: Session, ciclo_id: int) -> Dict[str, int]:
    """4 estados del ciclo (placeholder - adaptar a tu lógica)."""
    # Ejemplo: contar estanques por status
    # Necesitas definir qué significa cada "estado"
    return {
        "activos": 3,  # TODO: implementar lógica real
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
    """Curva de crecimiento del estanque individual."""
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
    """Curva de densidad del estanque individual."""
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        return []

    # Densidad inicial
    dens_base = _get_densidad_base_org_m2(db, ciclo_id, estanque_id)
    if not dens_base:
        return []

    # Eventos de cosecha
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

    # Punto inicial
    result.append({
        "semana": 0,
        "densidad_org_m2": dens_actual,
        "fecha": ciclo.fecha_inicio
    })

    # Puntos de cosecha
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