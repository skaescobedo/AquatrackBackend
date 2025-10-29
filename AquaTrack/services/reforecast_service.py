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
    """
    Factor de suavizado para interpolación.

    Args:
        t: Posición en el rango [0, 1]
        shape: Tipo de curva (linear, ease_in, ease_out, s_curve)

    Returns:
        Factor suavizado en [0, 1]
    """
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
    Encuentra índices de líneas con anclajes (notas con tag_prefix).
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


def _interpolate_series(values: List[float], anchors: List[int], shape: str) -> None:
    """Interpola serie completa entre anclajes (modifica in-place)"""
    if not values or len(values) <= 2:
        return

    anchors = sorted(set(anchors))

    # Asegurar que inicio y fin estén incluidos
    if 0 not in anchors:
        anchors.insert(0, 0)
    if (len(values) - 1) not in anchors:
        anchors.append(len(values) - 1)

    # Interpolar entre cada par de anclajes
    for i in range(len(anchors) - 1):
        _interpolate_segment(values, anchors[i], anchors[i + 1], shape)


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

    Args:
        soft_if_other_draft: Si True, retorna None si hay otro borrador (no lanza error)
    """
    # Verificar que el ciclo exista
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

    # Verificar si hay otro borrador (no reforecast)
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

    # Clonar desde proyección actual
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

    # Generar versión
    count = db.query(func.count(Proyeccion.proyeccion_id)).filter(
        Proyeccion.ciclo_id == ciclo_id
    ).scalar() or 0
    version = f"V{count + 1}"

    # Crear borrador
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

    # Buscar override en siembra_estanque
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

    # Usar densidad del plan
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
            CosechaEstanque.status == 'c'  # Solo confirmadas
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
    from datetime import time
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
    VERSION CON LOGS DETALLADOS PARA DEBUG.
    """
    print("\n" + "=" * 70)
    print(f"🔍 calc_farm_weighted_pp_sob INICIO")
    print("=" * 70)
    print(f"Parámetros:")
    print(f"  - ciclo_id: {ciclo_id}")
    print(f"  - fecha_inicio (date): {fecha_inicio}")
    print(f"  - fecha_fin (date): {fecha_fin}")

    # Obtener estanques
    ponds = _get_ponds_in_cycle(db, ciclo_id)
    total_ponds = len(ponds)

    print(f"\nEstanques encontrados: {total_ponds}")
    for p in ponds:
        print(f"  - Estanque {p.estanque_id}: {p.nombre} (área={p.superficie_m2}m²)")

    if total_ponds == 0:
        print("❌ NO HAY ESTANQUES VIGENTES EN LA GRANJA")
        return {
            "pp": None,
            "sob": None,
            "coverage_pct": 0.0,
            "measured_ponds": 0,
            "total_ponds": 0
        }

    plan = _get_siembra_plan(db, ciclo_id)

    if not plan:
        print("⚠️ NO HAY PLAN DE SIEMBRAS para este ciclo")
    else:
        print(f"\nPlan de siembras encontrado:")
        print(f"  - siembra_plan_id: {plan.siembra_plan_id}")
        print(f"  - densidad_base: {plan.densidad_org_m2} org/m²")

    # 🔧 Convertir date range a datetime range
    dt_inicio, dt_fin = _date_range_to_datetime(fecha_inicio, fecha_fin)

    print(f"\nVentana de búsqueda (datetime):")
    print(f"  - dt_inicio: {dt_inicio}")
    print(f"  - dt_fin: {dt_fin}")
    print()

    # Acumuladores
    pp_weighted_sum = Decimal("0")
    pp_weight_sum = Decimal("0")
    sob_weighted_sum = Decimal("0")
    sob_weight_sum = Decimal("0")
    measured_ponds = 0

    print("Procesando estanques:")
    print("-" * 70)

    for pond in ponds:
        print(f"\n🔸 Estanque {pond.estanque_id} ({pond.nombre}):")

        # Verificar siembra confirmada
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
            print(f"  ❌ NO tiene siembra confirmada (status='f')")
            continue
        else:
            print(f"  ✅ Tiene siembra confirmada (status='{siembra.status}')")

        # Buscar biometría
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
            print(f"  ❌ NO hay biometría en ventana")
            # Debug: buscar cualquier biometría
            any_bio = (
                db.query(Biometria)
                .filter(
                    Biometria.ciclo_id == ciclo_id,
                    Biometria.estanque_id == pond.estanque_id
                )
                .order_by(desc(Biometria.fecha))
                .first()
            )
            if any_bio:
                print(f"     (última bio registrada: {any_bio.fecha})")
            else:
                print(f"     (no hay ninguna biometría registrada)")
            continue

        print(f"  ✅ Biometría encontrada:")
        print(f"     - biometria_id: {bio.biometria_id}")
        print(f"     - fecha: {bio.fecha}")
        print(f"     - pp_g: {bio.pp_g}")
        print(f"     - sob_usada_pct: {bio.sob_usada_pct}")

        measured_ponds += 1

        # Obtener densidad base
        dens_base = _get_densidad_base(db, plan, pond.estanque_id)
        if dens_base is None:
            print(f"  ⚠️ NO se pudo obtener densidad base")
            continue

        if pond.superficie_m2 is None:
            print(f"  ⚠️ Estanque sin superficie_m2 definida")
            continue

        print(f"     - densidad_base: {dens_base} org/m²")
        print(f"     - área: {pond.superficie_m2} m²")

        # Calcular retiros
        retiros = _get_retiros_acumulados(db, ciclo_id, pond.estanque_id)
        dens_restante = dens_base - retiros
        if dens_restante < Decimal("0"):
            dens_restante = Decimal("0")

        print(f"     - retiros_acumulados: {retiros} org/m²")
        print(f"     - densidad_restante: {dens_restante} org/m²")

        area = Decimal(str(pond.superficie_m2))
        peso_base = dens_restante * area

        print(f"     - organismos_estimados: {float(peso_base):.0f}")

        # Ponderar SOB
        if bio.sob_usada_pct is not None:
            sob_val = Decimal(str(bio.sob_usada_pct))
            sob_weighted_sum += sob_val * peso_base
            sob_weight_sum += peso_base
            print(
                f"     - Contribución a SOB: {float(sob_val):.2f}% × {float(peso_base):.0f} = {float(sob_val * peso_base):.0f}")

        # Ponderar PP
        if bio.pp_g is not None and bio.sob_usada_pct is not None:
            org_estimados = peso_base * (Decimal(str(bio.sob_usada_pct)) / Decimal("100"))
            pp_weighted_sum += Decimal(str(bio.pp_g)) * org_estimados
            pp_weight_sum += org_estimados
            print(
                f"     - Contribución a PP: {float(bio.pp_g):.3f}g × {float(org_estimados):.0f} = {float(Decimal(str(bio.pp_g)) * org_estimados):.0f}")

    # Calcular promedios ponderados
    print("\n" + "=" * 70)
    print("📊 CÁLCULO FINAL:")
    print("-" * 70)

    pp_avg = float(pp_weighted_sum / pp_weight_sum) if pp_weight_sum > 0 else None
    sob_avg = float(sob_weighted_sum / sob_weight_sum) if sob_weight_sum > 0 else None
    coverage = (measured_ponds / total_ponds * 100.0) if total_ponds > 0 else 0.0

    print(f"PP ponderado:")
    print(f"  - Suma ponderada: {float(pp_weighted_sum):.3f}")
    print(f"  - Peso total: {float(pp_weight_sum):.0f}")
    print(f"  - Promedio: {pp_avg:.3f}g" if pp_avg else "  - Promedio: None")

    print(f"\nSOB ponderado:")
    print(f"  - Suma ponderada: {float(sob_weighted_sum):.2f}")
    print(f"  - Peso total: {float(sob_weight_sum):.0f}")
    print(f"  - Promedio: {sob_avg:.2f}%" if sob_avg else "  - Promedio: None")

    print(f"\nCobertura:")
    print(f"  - Estanques medidos: {measured_ponds}")
    print(f"  - Estanques totales: {total_ponds}")
    print(f"  - Cobertura: {coverage:.1f}%")

    result = {
        "pp": round(pp_avg, 3) if pp_avg else None,
        "sob": round(sob_avg, 2) if sob_avg else None,
        "coverage_pct": round(coverage, 2),
        "measured_ponds": measured_ponds,
        "total_ponds": total_ponds
    }

    print(f"\n✅ RESULTADO FINAL: {result}")
    print("=" * 70 + "\n")

    return result


def _get_weekend_window(event_date: date) -> Tuple[date, date, date]:
    """
    Calcula ventana de fin de semana (Sábado-Domingo).

    Returns:
        (sabado, domingo, anchor=domingo)
    """
    # Calcular lunes de la semana
    monday = event_date - timedelta(days=event_date.weekday())
    saturday = monday + timedelta(days=5)  # Sábado
    sunday = monday + timedelta(days=6)  # Domingo

    return saturday, sunday, sunday  # Anclar en domingo


# ===================================
# TRIGGER 1: BIOMETRÍAS
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
    Trigger de reforecast después de registrar biometría.

    ✅ FIX: Agregado db.add(ln) para forzar persistencia de cambios
    """
    # Verificar master switch
    if not settings.REFORECAST_ENABLED:
        return {"skipped": True, "reason": "reforecast_disabled"}

    # Obtener/crear borrador
    draft = get_or_create_reforecast_draft(
        db, user, ciclo_id,
        soft_if_other_draft=soft_if_other_draft
    )

    if draft is None:
        return {"skipped": True, "reason": "other_draft_exists"}

    # Determinar ventana de agregación
    if settings.REFORECAST_WEEKEND_MODE:
        fecha_inicio, fecha_fin, anchor_date = _get_weekend_window(fecha_bio)
    else:
        radius = timedelta(days=settings.REFORECAST_WINDOW_DAYS)
        fecha_inicio = fecha_bio - radius
        fecha_fin = fecha_bio + radius
        anchor_date = fecha_bio

    # Agregar datos de granja
    agg = calc_farm_weighted_pp_sob(db, ciclo_id, fecha_inicio, fecha_fin)

    # Validar umbrales
    if agg["total_ponds"] == 0:
        return {"skipped": True, "reason": "no_ponds", "agg": agg}

    if agg["measured_ponds"] < settings.REFORECAST_MIN_PONDS:
        return {"skipped": True, "reason": "below_min_ponds", "agg": agg}

    if agg["coverage_pct"] < settings.REFORECAST_MIN_COVERAGE_PCT:
        return {"skipped": True, "reason": "below_coverage_threshold", "agg": agg}

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

    # Encontrar semana más cercana
    week_idx = _nearest_week_index(lines, anchor_date)
    target_line = lines[week_idx]

    # Anclar valores reales
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

    # Extraer series
    pp_series = [float(ln.pp_g) for ln in lines]
    sob_series = [float(ln.sob_pct_linea) for ln in lines]

    # Encontrar anclajes
    pp_anchors = _anchor_indexes(lines, "obs_pp:")
    sob_anchors = _anchor_indexes(lines, "obs_sob:")

    # Interpolar solo futuro
    _interpolate_series(pp_series, pp_anchors, shape="s_curve")
    _interpolate_series(sob_series, sob_anchors, shape="linear")

    # ✅ FIX: Actualizar líneas Y FORZAR PERSISTENCIA
    for i, ln in enumerate(lines):
        ln.pp_g = round(pp_series[i], 3)
        ln.sob_pct_linea = round(max(0.0, min(100.0, sob_series[i])), 2)
        db.add(ln)  # ← CRÍTICO: Forzar que SQLAlchemy detecte cambios

    # Recalcular incrementos
    increments = _recalc_increments(pp_series)
    for i, ln in enumerate(lines):
        ln.incremento_g_sem = increments[i]
        db.add(ln)  # ← CRÍTICO: También aquí

    # Recalcular SOB Final Objetivo
    sob_final_anterior = draft.sob_final_objetivo_pct
    if agg["sob"] is not None:
        sob_final_nuevo = calc_sob_final_objetivo(db, ciclo_id, draft)
        draft.sob_final_objetivo_pct = sob_final_nuevo

        print(f"\n📊 SOB Final Objetivo:")
        print(f"  - Anterior: {sob_final_anterior:.2f}%" if sob_final_anterior else "  - Anterior: None")
        print(f"  - Nuevo (recalculado): {sob_final_nuevo:.2f}%")
        if sob_final_anterior:
            delta = sob_final_nuevo - float(sob_final_anterior)
            print(f"  - Δ: {delta:+.2f}%")

    # Actualizar timestamp
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
    Trigger de reforecast después de confirmar o reprogramar siembra.

    Proceso:
    1. Verificar que reforecast esté habilitado
    2. Calcular delta = fecha_real - fecha_tentativa
    3. Si delta == 0, no hacer nada
    4. Obtener/crear borrador de reforecast
    5. Shift TODAS las fecha_plan += delta
    6. Mantener edad_dias (0, 7, 14, ...)
    7. Actualizar siembra_ventana_fin si aplica

    Args:
        fecha_siembra_real: Fecha confirmada/reprogramada
        fecha_siembra_tentativa: Fecha original planeada
        soft_if_other_draft: Si True, no lanza error si hay otro borrador

    Returns:
        {
            skipped: bool,
            reason: str | None,
            proyeccion_id: int | None,
            delta_days: int,
            lines_updated: int
        }
    """
    # Verificar master switch
    if not settings.REFORECAST_ENABLED:
        return {"skipped": True, "reason": "reforecast_disabled"}

    # Calcular delta
    delta_days = (fecha_siembra_real - fecha_siembra_tentativa).days

    if delta_days == 0:
        return {"skipped": True, "reason": "no_date_change", "delta_days": 0}

    # Obtener/crear borrador
    draft = get_or_create_reforecast_draft(
        db, user, ciclo_id,
        soft_if_other_draft=soft_if_other_draft
    )

    if draft is None:
        return {"skipped": True, "reason": "other_draft_exists"}

    # Obtener líneas del borrador
    lines: List[ProyeccionLinea] = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    if not lines:
        return {"skipped": True, "reason": "no_lines_in_draft"}

    # Shift todas las fechas
    delta = timedelta(days=delta_days)
    for ln in lines:
        ln.fecha_plan = ln.fecha_plan + delta

    # Actualizar siembra_ventana_fin si existe
    if draft.siembra_ventana_fin:
        draft.siembra_ventana_fin = draft.siembra_ventana_fin + delta

    # Actualizar timestamp
    draft.updated_at = now_mazatlan()

    # Agregar nota en primera línea
    first_line = lines[0]
    note_parts = []
    if first_line.nota:
        note_parts.append(first_line.nota)
    note_parts.append(f"shift_siembra:{delta_days}d")
    first_line.nota = " | ".join(note_parts)

    db.commit()

    return {
        "skipped": False,
        "proyeccion_id": draft.proyeccion_id,
        "delta_days": delta_days,
        "lines_updated": len(lines),
        "new_start_date": lines[0].fecha_plan if lines else None
    }


# ===================================
# TRIGGER 3: COSECHAS (ajuste retiros y SOB)
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
    Trigger de reforecast después de confirmar cosecha.

    Proceso:
    1. Verificar que reforecast esté habilitado
    2. Obtener/crear borrador de reforecast
    3. Encontrar línea con cosecha_flag cercana a fecha_cosecha_real
    4. Actualizar fecha_plan y retiro_org_m2
    5. Recalcular SOB desde esa semana hacia adelante
    6. Actualizar sob_final_objetivo_pct

    Args:
        fecha_cosecha_real: Fecha en que se confirmó la cosecha
        densidad_retirada_org_m2: Densidad real retirada
        soft_if_other_draft: Si True, no lanza error si hay otro borrador

    Returns:
        {
            skipped: bool,
            reason: str | None,
            proyeccion_id: int | None,
            harvest_week_idx: int | None,
            sob_final_updated: float | None
        }
    """
    # Verificar master switch
    if not settings.REFORECAST_ENABLED:
        return {"skipped": True, "reason": "reforecast_disabled"}

    # Obtener/crear borrador
    draft = get_or_create_reforecast_draft(
        db, user, ciclo_id,
        soft_if_other_draft=soft_if_other_draft
    )

    if draft is None:
        return {"skipped": True, "reason": "other_draft_exists"}

    # Obtener líneas del borrador
    lines: List[ProyeccionLinea] = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx))
        .all()
    )

    if not lines:
        return {"skipped": True, "reason": "no_lines_in_draft"}

    # Buscar línea de cosecha más cercana
    harvest_lines = [i for i, ln in enumerate(lines) if ln.cosecha_flag]

    if not harvest_lines:
        return {"skipped": True, "reason": "no_harvest_line_in_projection"}

    # Encontrar la más cercana a fecha_cosecha_real
    best_idx = harvest_lines[0]
    best_diff = abs((lines[best_idx].fecha_plan - fecha_cosecha_real).days)

    for idx in harvest_lines:
        diff = abs((lines[idx].fecha_plan - fecha_cosecha_real).days)
        if diff < best_diff:
            best_diff = diff
            best_idx = idx

    harvest_line = lines[best_idx]

    # Actualizar fecha y retiro
    harvest_line.fecha_plan = fecha_cosecha_real
    harvest_line.retiro_org_m2 = round(densidad_retirada_org_m2, 4)

    # Agregar nota
    note_parts = []
    if harvest_line.nota:
        note_parts.append(harvest_line.nota)
    note_parts.append(f"obs_cosecha:{densidad_retirada_org_m2:.2f}org/m2")
    harvest_line.nota = " | ".join(note_parts)

    # Recalcular SOB desde esta semana hacia adelante
    # Fórmula: SOB_después = SOB_antes * (1 - retiro/densidad_base)
    plan = _get_siembra_plan(db, ciclo_id)
    if plan and plan.densidad_org_m2:
        dens_base = float(plan.densidad_org_m2)
        retiro_ratio = densidad_retirada_org_m2 / dens_base

        # Ajustar SOB desde cosecha hacia adelante
        for i in range(best_idx + 1, len(lines)):
            sob_antes = lines[i - 1].sob_pct_linea
            sob_despues = sob_antes * (1 - retiro_ratio)
            lines[i].sob_pct_linea = round(max(0.0, min(100.0, sob_despues)), 2)

    # Recalcular sob_final_objetivo_pct
    sob_final = calc_sob_final_objetivo(db, ciclo_id, draft)
    draft.sob_final_objetivo_pct = sob_final

    # Actualizar timestamp
    draft.updated_at = now_mazatlan()

    db.commit()

    return {
        "skipped": False,
        "proyeccion_id": draft.proyeccion_id,
        "harvest_week_idx": best_idx,
        "sob_final_updated": sob_final,
        "lines_updated": len(lines) - best_idx  # Solo desde cosecha hacia adelante
    }


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

    LÓGICA CORRECTA:
    - Los retiros NO afectan el SOB (son organismos vivos cosechados)
    - El SOB final objetivo refleja mortalidad acumulada esperada
    - Si el SOB actual es mejor/peor que lo planeado, ajustamos proporcionalmente

    Algoritmo:
    1. Obtener SOB final objetivo de la proyección padre (baseline)
    2. Encontrar última línea con SOB observado real
    3. Comparar SOB real vs SOB planeado en esa semana (de la proyección padre)
    4. Calcular factor de ajuste = SOB_real / SOB_planeado
    5. Aplicar factor al SOB final objetivo: SOB_final_ajustado = SOB_final_original × factor

    Ejemplo:
    - Proyección padre: sem 0 = 100% → sem 14 = 78% (sob_final_objetivo)
    - Biometría real: sem 0 = 98.5% (1.5% de mortalidad extra)
    - Factor: 98.5 / 100 = 0.985
    - SOB final ajustado: 78 × 0.985 = 76.83%

    Returns:
        SOB final estimado ajustado (0-100)
    """
    print("\n" + "=" * 70)
    print("🔍 calc_sob_final_objetivo - INICIO")
    print("=" * 70)

    # 1. Obtener SOB final objetivo de la proyección PADRE (baseline)
    if not draft.parent_version_id:
        print("⚠️ No hay proyección padre, usando SOB de última línea del draft")
        last_line = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == draft.proyeccion_id)
            .order_by(desc(ProyeccionLinea.semana_idx))
            .first()
        )
        result = float(last_line.sob_pct_linea) if last_line else 85.0
        print(f"📊 Usando fallback: {result:.2f}%")
        return result

    parent = db.get(Proyeccion, draft.parent_version_id)
    if not parent or not parent.sob_final_objetivo_pct:
        print("⚠️ Proyección padre sin sob_final_objetivo_pct")
        return 85.0

    sob_final_original = Decimal(str(parent.sob_final_objetivo_pct))
    print(f"📌 SOB final objetivo original (padre): {float(sob_final_original):.2f}%")

    # 2. Obtener líneas del draft y del padre
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
        print("⚠️ No hay líneas en draft o padre")
        return float(sob_final_original)

    # 3. Buscar último SOB observado en el draft
    sob_real = None
    semana_observada = None

    for i, ln in enumerate(draft_lines):
        if ln.nota and "obs_sob:" in ln.nota:
            sob_real = Decimal(str(ln.sob_pct_linea))
            semana_observada = i
            print(f"✅ Último SOB observado: {float(sob_real):.2f}% (semana {i})")
            break

    if sob_real is None:
        print("ℹ️ No hay SOB observado, manteniendo SOB final objetivo original")
        return float(sob_final_original)

    # 4. Obtener SOB planeado en esa misma semana (del padre)
    if semana_observada >= len(parent_lines):
        print(f"⚠️ Semana {semana_observada} no existe en proyección padre")
        return float(sob_final_original)

    sob_planeado = Decimal(str(parent_lines[semana_observada].sob_pct_linea))
    print(f"📋 SOB planeado en semana {semana_observada} (padre): {float(sob_planeado):.2f}%")

    # 5. Calcular factor de ajuste
    if sob_planeado == 0:
        print("⚠️ SOB planeado es 0, no se puede calcular factor")
        return float(sob_final_original)

    factor_ajuste = sob_real / sob_planeado
    print(f"\n📊 Análisis de desviación:")
    print(f"  - SOB real: {float(sob_real):.2f}%")
    print(f"  - SOB planeado: {float(sob_planeado):.2f}%")
    print(f"  - Factor de ajuste: {float(factor_ajuste):.4f}")

    if factor_ajuste > Decimal("1"):
        print(f"  ✅ Mortalidad MENOR que lo esperado (+{float((factor_ajuste - 1) * 100):.2f}%)")
    elif factor_ajuste < Decimal("1"):
        print(f"  ⚠️ Mortalidad MAYOR que lo esperado ({float((factor_ajuste - 1) * 100):.2f}%)")
    else:
        print(f"  ➡️ Mortalidad según lo planeado")

    # 6. Aplicar factor al SOB final objetivo
    sob_final_ajustado = sob_final_original * factor_ajuste
    sob_final_ajustado = max(Decimal("0"), min(Decimal("100"), sob_final_ajustado))

    result = float(sob_final_ajustado)

    print(f"\n🎯 Cálculo del SOB Final Objetivo:")
    print(f"  - SOB final original: {float(sob_final_original):.2f}%")
    print(f"  - Factor de ajuste: {float(factor_ajuste):.4f}")
    print(f"  - SOB final ajustado: {result:.2f}%")
    print(f"  - Δ: {result - float(sob_final_original):+.2f}%")
    print("=" * 70 + "\n")

    return result