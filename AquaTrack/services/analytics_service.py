# services/analytics_service.py
"""
Servicio de analytics para preparar datos de dashboards.
Consumido por api/analytics_routes.py

MEJORAS:
- Prioridad: borrador > publicado (para mostrar datos más actuales)
- Estados dinámicos (no hardcodeados)
- Biomasa evolutiva correcta (por semana, con PP inicial en semana 0)
- Fuentes de datos (pp_fuente, sob_fuente, pp_updated_at)
- Sample sizes (metadata de cuántos estanques contribuyen)
- SIN validaciones de permisos (se hacen en el router)
- CORREGIDO: Acumulación de retiros proyectados (una sola vez por semana)
"""
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc

from utils.datetime_utils import today_mazatlan
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
            SiembraEstanque.status == "f"  # ← Solo confirmadas
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
    Obtiene la MEJOR proyección disponible.

    NUEVO: Prioridad:
    1. Borrador más reciente (status='b')
    2. Proyección actual publicada (is_current=True, status='p')

    Razón: El borrador tiene datos más actualizados que el usuario está trabajando.
    """
    # 1. Intentar borrador
    draft = (
        db.query(Proyeccion)
        .filter(
            Proyeccion.ciclo_id == ciclo_id,
            Proyeccion.status == 'b'
        )
        .order_by(desc(Proyeccion.created_at))
        .first()
    )
    if draft:
        return draft

    # 2. Proyección publicada actual
    return (
        db.query(Proyeccion)
        .filter(
            Proyeccion.ciclo_id == ciclo_id,
            Proyeccion.is_current == True,
            Proyeccion.status == 'p'
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
    dias_cultivo = (today_mazatlan() - ciclo.fecha_inicio).days
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


# ==================== GRÁFICAS ====================

def get_growth_curve_data(db: Session, ciclo_id: int) -> List[Dict[str, Any]]:
    """Serie temporal de PP promedio del ciclo (real + proyectado)."""
    proj = _get_best_projection(db, ciclo_id)
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
    Serie temporal de biomasa acumulada CORRECTA.

    ALGORITMO FINAL:
    1. SOB es acumulado desde inicio (ya incluye toda la mortalidad histórica)
    2. Retiros son acumulativos y permanentes
    3. Retiros confirmados tienen prioridad sobre proyectados
    4. Retiros proyectados se aplican UNA VEZ por semana (no por estanque)
    5. La última semana (cosecha final) muestra biomasa PRE-COSECHA

    FÓRMULA: biomasa = superficie × (densidad_base × sob_acum / 100 - retiros_acum) × pp
    """
    proj = _get_best_projection(db, ciclo_id)
    if not proj:
        return []

    lineas = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == proj.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    if not lineas or not pond_snapshots:
        return []

    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        return []

    # Obtener cosechas confirmadas por estanque y fecha
    cosechas_confirmadas = (
        db.query(
            CosechaEstanque.estanque_id,
            CosechaOla.ventana_inicio,
            CosechaEstanque.densidad_retirada_org_m2
        )
        .join(CosechaOla, CosechaEstanque.cosecha_ola_id == CosechaOla.cosecha_ola_id)
        .filter(
            CosechaOla.ciclo_id == ciclo_id,
            CosechaEstanque.status == 'c'
        )
        .all()
    )

    # Mapear retiros confirmados: {estanque_id: [(fecha, densidad), ...]}
    retiros_confirmados: Dict[int, List[tuple[date, Decimal]]] = {}
    for c in cosechas_confirmadas:
        if c.estanque_id not in retiros_confirmados:
            retiros_confirmados[c.estanque_id] = []
        retiros_confirmados[c.estanque_id].append((c.ventana_inicio, Decimal(str(c.densidad_retirada_org_m2))))

    result = []

    # Rastrear retiros acumulados por estanque
    retiros_acum_por_estanque: Dict[int, Decimal] = {
        snap["estanque_id"]: Decimal("0") for snap in pond_snapshots
    }

    # Identificar la última semana (cosecha final)
    ultima_semana_idx = lineas[-1].semana_idx if lineas else None

    for line in lineas:
        # Verificar si esta es la última semana Y tiene cosecha final
        es_cosecha_final = (line.semana_idx == ultima_semana_idx and line.cosecha_flag)

        # ✅ PASO 1: Aplicar retiros proyectados UNA VEZ (antes del loop de estanques)
        # PERO NO aplicar si es la cosecha final (queremos mostrar biomasa PRE-cosecha)
        if line.cosecha_flag and line.retiro_org_m2 and not es_cosecha_final:
            # Verificar si esta fecha tiene retiros confirmados en algún estanque
            fechas_confirmadas = set()
            for retiros_est in retiros_confirmados.values():
                for fecha_ret, _ in retiros_est:
                    fechas_confirmadas.add(fecha_ret)

            # Solo aplicar retiro proyectado si NO hay confirmados en esta fecha
            if line.fecha_plan not in fechas_confirmadas:
                for est_id in retiros_acum_por_estanque.keys():
                    retiros_acum_por_estanque[est_id] += Decimal(str(line.retiro_org_m2))

        # PASO 2: Calcular biomasa por estanque
        biomasa_semana = Decimal("0")

        for snap in pond_snapshots:
            estanque_id = snap["estanque_id"]
            superficie = Decimal(str(snap["superficie_m2"]))
            dens_base = Decimal(str(snap["densidad_base_org_m2"]))

            # Verificar si hay retiros confirmados hasta esta fecha
            retiros_confirmados_acum = Decimal("0")
            for fecha_ret, dens_ret in retiros_confirmados.get(estanque_id, []):
                if fecha_ret <= line.fecha_plan:
                    retiros_confirmados_acum += dens_ret

            # Los retiros confirmados REEMPLAZAN los proyectados
            if retiros_confirmados_acum > 0:
                retiros_acum_por_estanque[estanque_id] = retiros_confirmados_acum

            # ORDEN CORRECTO: Primero SOB, luego retiros
            # 1. Aplicar SOB acumulado a densidad base
            sob_pct = Decimal(str(line.sob_pct_linea))
            dens_con_sob = dens_base * (sob_pct / Decimal("100"))

            # 2. Restar retiros acumulados
            retiros_acum = retiros_acum_por_estanque[estanque_id]
            dens_viva = dens_con_sob - retiros_acum
            if dens_viva < 0:
                dens_viva = Decimal("0")

            # 3. Calcular biomasa
            org_vivos = dens_viva * superficie
            pp_g = Decimal(str(line.pp_g))
            biomasa_est = calculate_biomasa_kg(org_vivos, pp_g)
            biomasa_semana += biomasa_est

        result.append({
            "semana": line.semana_idx,
            "biomasa_kg": round(float(biomasa_semana), 1),
            "fecha": line.fecha_plan
        })

    return result


def get_density_evolution_data(db: Session, ciclo_id: int) -> List[Dict[str, Any]]:
    """
    Serie temporal de densidad promedio CORRECTA.

    ALGORITMO CORREGIDO:
    - Los retiros son ACUMULATIVOS (una vez retirado, no vuelve)
    - Considera retiros confirmados (status='c')
    - Considera retiros de la proyección (cosecha_flag + retiro_org_m2)
    - El camarón no revive entre semanas
    """
    proj = _get_best_projection(db, ciclo_id)
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

    # Obtener retiros confirmados
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

    # Mapear retiros confirmados por fecha
    retiros_confirmados_map = {c.ventana_inicio: float(c.retiro_promedio) for c in cosechas_confirmadas}

    result = []
    retiro_acumulado = 0.0  # Rastrear retiros acumulados

    for line in lineas:
        # Aplicar SOB a la densidad base
        dens_viva = dens_inicial * (float(line.sob_pct_linea) / 100)

        # 1. RETIROS CONFIRMADOS: Si hay retiro confirmado en esta fecha
        if line.fecha_plan in retiros_confirmados_map:
            retiro_acumulado += retiros_confirmados_map[line.fecha_plan]

        # 2. RETIROS PROYECTADOS: Si hay cosecha planificada (cosecha_flag)
        elif line.cosecha_flag and line.retiro_org_m2:
            retiro_acumulado += float(line.retiro_org_m2)

        # Restar retiros acumulados (permanentes)
        dens_viva -= retiro_acumulado

        # No permitir densidad negativa
        if dens_viva < 0:
            dens_viva = 0

        result.append({
            "semana": line.semana_idx,
            "densidad_org_m2": round(dens_viva, 2),
            "fecha": line.fecha_plan
        })

    return result


# ==================== OPERACIONES PRÓXIMAS ====================

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
    today = today_mazatlan()
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
    """
    Estados dinámicos de estanques del ciclo.

    NUEVO: Lógica dinámica (no hardcodeado).
    """
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


def _get_pond_growth_curve(db: Session, ciclo_id: int, estanque_id: int) -> List[Dict[str, Any]]:
    """Curva de crecimiento del estanque."""
    bios = (
        db.query(Biometria)
        .filter(
            Biometria.ciclo_id == ciclo_id,
            Biometria.estanque_id == estanque_id
        )
        .order_by(asc(Biometria.fecha))
        .all()
    )

    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        return []

    result = []
    for bio in bios:
        dias = (bio.fecha.date() - ciclo.fecha_inicio).days
        semana = dias // 7
        result.append({
            "semana": semana,
            "pp_g": float(bio.pp_g),
            "fecha": bio.fecha.date()
        })

    return result


def _get_pond_density_curve(db: Session, ciclo_id: int, estanque_id: int) -> List[Dict[str, Any]]:
    """Evolución de densidad del estanque."""
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
        .order_by(asc(CosechaOla.ventana_inicio))
        .all()
    )

    result = []
    dens_actual = float(dens_base)

    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        return []

    # Punto inicial
    result.append({
        "semana": 0,
        "densidad_org_m2": dens_actual,
        "fecha": ciclo.fecha_inicio
    })

    for cosecha in cosechas:
        dens_actual -= float(cosecha.densidad_retirada_org_m2)
        ola = db.get(CosechaOla, cosecha.cosecha_ola_id)
        if ola:
            dias = (ola.ventana_inicio - ciclo.fecha_inicio).days
            semana = dias // 7
            result.append({
                "semana": semana,
                "densidad_org_m2": round(dens_actual, 2),
                "fecha": ola.ventana_inicio
            })

    return result