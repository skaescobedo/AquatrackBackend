"""
Servicio de cálculos matemáticos y métricas agregadas.
No tiene endpoints propios - es consumido por otros servicios y rutas.
"""
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from datetime import date


# ==================== CÁLCULOS DE DENSIDAD Y BIOMASA ====================

def calculate_densidad_viva(
        densidad_base: Decimal,
        densidad_retirada: Decimal,
        sob_pct: Decimal
) -> Decimal:
    """
    Calcula densidad viva de organismos.
    densidad_viva = (densidad_base - densidad_retirada) × (SOB% / 100)
    """
    densidad_remanente = densidad_base - densidad_retirada
    if densidad_remanente < Decimal("0"):
        densidad_remanente = Decimal("0")

    return (densidad_remanente * (sob_pct / Decimal("100"))).quantize(Decimal("0.0001"))


def calculate_org_vivos(
        densidad_viva_org_m2: Decimal,
        superficie_m2: Decimal
) -> Decimal:
    """
    Calcula organismos vivos totales en un estanque.
    org_vivos = densidad_viva × superficie
    """
    return (densidad_viva_org_m2 * superficie_m2).quantize(Decimal("0.0001"))


def calculate_biomasa_kg(
        org_vivos: Decimal,
        pp_g: Decimal
) -> Decimal:
    """
    Calcula biomasa en kilogramos.
    biomasa = org_vivos × (pp_g / 1000)
    """
    return (org_vivos * (pp_g / Decimal("1000"))).quantize(Decimal("0.1"))


# ==================== AGREGACIONES PONDERADAS ====================

def calculate_weighted_density(pond_data: List[Dict[str, Any]]) -> Optional[Decimal]:
    """
    Densidad viva promedio ponderada por superficie.

    pond_data debe contener: densidad_viva_org_m2, superficie_m2
    """
    total_superficie = Decimal("0")
    weighted_sum = Decimal("0")

    for pond in pond_data:
        if pond.get("densidad_viva_org_m2") is None or pond.get("superficie_m2") is None:
            continue

        dens = Decimal(str(pond["densidad_viva_org_m2"]))
        sup = Decimal(str(pond["superficie_m2"]))

        total_superficie += sup
        weighted_sum += (dens * sup)

    if total_superficie <= 0:
        return None

    return (weighted_sum / total_superficie).quantize(Decimal("0.0001"))


def calculate_global_sob(pond_data: List[Dict[str, Any]]) -> Optional[Decimal]:
    """
    SOB global del ciclo: vivos totales / remanente total (pre-SOB).

    pond_data debe contener: densidad_viva_org_m2, sob_vigente_pct, superficie_m2
    """
    total_vivos = Decimal("0")
    total_remanente_pre_sob = Decimal("0")

    for pond in pond_data:
        if (pond.get("densidad_viva_org_m2") is None or
                pond.get("sob_vigente_pct") is None or
                pond.get("superficie_m2") is None):
            continue

        dens_viva = Decimal(str(pond["densidad_viva_org_m2"]))
        sob_pct = Decimal(str(pond["sob_vigente_pct"]))
        sup = Decimal(str(pond["superficie_m2"]))

        if sob_pct <= 0:
            continue

        # Reconstruir remanente pre-SOB
        dens_remanente = dens_viva / (sob_pct / Decimal("100"))

        total_vivos += (dens_viva * sup)
        total_remanente_pre_sob += (dens_remanente * sup)

    if total_remanente_pre_sob <= 0:
        return None

    return ((total_vivos / total_remanente_pre_sob) * Decimal("100")).quantize(Decimal("0.01"))


def calculate_weighted_pp(pond_data: List[Dict[str, Any]]) -> Optional[Decimal]:
    """
    PP promedio ponderado por organismos vivos.
    Solo considera estanques con PP y org_vivos válidos.

    pond_data debe contener: pp_vigente_g, org_vivos_est
    """
    weighted_sum = Decimal("0")
    total_org = Decimal("0")

    for pond in pond_data:
        if pond.get("pp_vigente_g") is None or pond.get("org_vivos_est") is None:
            continue

        pp = Decimal(str(pond["pp_vigente_g"]))
        org = Decimal(str(pond["org_vivos_est"]))

        weighted_sum += (pp * org)
        total_org += org

    if total_org <= 0:
        return None

    return (weighted_sum / total_org).quantize(Decimal("0.01"))


def calculate_total_biomass(pond_data: List[Dict[str, Any]]) -> Decimal:
    """
    Suma biomasa total de todos los estanques.

    pond_data debe contener: biomasa_est_kg
    """
    total = Decimal("0")

    for pond in pond_data:
        if pond.get("biomasa_est_kg") is not None:
            total += Decimal(str(pond["biomasa_est_kg"]))

    return total.quantize(Decimal("0.1"))


# ==================== CONVERSIÓN ALIMENTICIA (FCR) ====================

def calculate_fcr(
        alimento_consumido_kg: Decimal,
        biomasa_ganada_kg: Decimal
) -> Optional[Decimal]:
    """
    Factor de Conversión Alimenticia.
    FCR = alimento_consumido / biomasa_ganada

    Valores típicos: 1.0-1.8 (menor es mejor)
    """
    if biomasa_ganada_kg <= 0:
        return None

    return (alimento_consumido_kg / biomasa_ganada_kg).quantize(Decimal("0.01"))


def calculate_fcr_accumulated(
        alimento_total_kg: Decimal,
        biomasa_actual_kg: Decimal,
        biomasa_inicial_kg: Decimal
) -> Optional[Decimal]:
    """
    FCR acumulado del ciclo completo.
    FCR = alimento_total / (biomasa_actual - biomasa_inicial)
    """
    biomasa_ganada = biomasa_actual_kg - biomasa_inicial_kg

    if biomasa_ganada <= 0:
        return None

    return (alimento_total_kg / biomasa_ganada).quantize(Decimal("0.01"))


# ==================== DESVIACIONES Y PROYECCIONES ====================

def calculate_deviation_pct(
        valor_real: Decimal,
        valor_proyectado: Decimal
) -> Optional[Decimal]:
    """
    Calcula desviación porcentual: ((real - proyectado) / proyectado) × 100
    Retorna None si proyectado es 0.

    Positivo = por encima de proyección
    Negativo = por debajo de proyección
    """
    if valor_proyectado == 0:
        return None

    return (((valor_real - valor_proyectado) / valor_proyectado) * Decimal("100")).quantize(Decimal("0.01"))


def calculate_growth_rate(
        pp_final_g: Decimal,
        pp_inicial_g: Decimal,
        dias_transcurridos: int
) -> Optional[Decimal]:
    """
    Tasa de crecimiento en gramos por semana.
    growth_rate = ((pp_final - pp_inicial) / dias) × 7
    """
    if dias_transcurridos <= 0 or pp_inicial_g <= 0:
        return None

    ganancia_diaria = (pp_final_g - pp_inicial_g) / Decimal(str(dias_transcurridos))
    ganancia_semanal = ganancia_diaria * Decimal("7")

    return ganancia_semanal.quantize(Decimal("0.01"))


def calculate_yield_projection(
        org_vivos: Decimal,
        pp_actual_g: Decimal,
        pp_cosecha_g: Decimal
) -> Decimal:
    """
    Proyección de biomasa en cosecha.
    yield = org_vivos × (pp_cosecha / 1000)

    Asume que la supervivencia se mantiene constante.
    """
    return (org_vivos * (pp_cosecha_g / Decimal("1000"))).quantize(Decimal("0.1"))


def calculate_days_to_target_weight(
        pp_actual_g: Decimal,
        pp_objetivo_g: Decimal,
        growth_rate_g_week: Decimal
) -> Optional[int]:
    """
    Días estimados para alcanzar peso objetivo.
    dias = ((pp_objetivo - pp_actual) / growth_rate) × 7
    """
    if growth_rate_g_week <= 0:
        return None

    pp_faltante = pp_objetivo_g - pp_actual_g
    if pp_faltante <= 0:
        return 0

    semanas = pp_faltante / growth_rate_g_week
    dias = (semanas * Decimal("7")).quantize(Decimal("1"))

    return int(dias)


# ==================== RENDIMIENTO Y EFICIENCIA ====================

def calculate_survival_rate(
        org_actuales: Decimal,
        org_sembrados: Decimal
) -> Optional[Decimal]:
    """
    Tasa de supervivencia actual.
    sob% = (org_actuales / org_sembrados) × 100
    """
    if org_sembrados <= 0:
        return None

    return ((org_actuales / org_sembrados) * Decimal("100")).quantize(Decimal("0.01"))


def calculate_density_efficiency(
        biomasa_kg: Decimal,
        superficie_m2: Decimal
) -> Decimal:
    """
    Biomasa por unidad de área (kg/m²).
    Indicador de eficiencia del uso del espacio.
    """
    if superficie_m2 <= 0:
        return Decimal("0")

    return (biomasa_kg / superficie_m2).quantize(Decimal("0.01"))


def calculate_productivity_index(
        biomasa_kg: Decimal,
        dias_cultivo: int,
        superficie_ha: Decimal
) -> Optional[Decimal]:
    """
    Índice de productividad: kg / (ha × dias)
    Métrica para comparar ciclos de diferente duración.
    """
    if dias_cultivo <= 0 or superficie_ha <= 0:
        return None

    return (biomasa_kg / (superficie_ha * Decimal(str(dias_cultivo)))).quantize(Decimal("0.01"))


# ==================== ANÁLISIS DE COSECHA ====================

def calculate_harvest_yield(
        org_cosechados: Decimal,
        pp_cosecha_g: Decimal
) -> Decimal:
    """
    Biomasa cosechada en kg.
    yield = org_cosechados × (pp_cosecha / 1000)
    """
    return (org_cosechados * (pp_cosecha_g / Decimal("1000"))).quantize(Decimal("0.1"))


def calculate_size_distribution(sizes_g: List[Decimal]) -> Dict[str, Any]:
    """
    Distribución de tallas (min, max, promedio, desviación estándar).
    """
    if not sizes_g:
        return {
            "min_g": None,
            "max_g": None,
            "promedio_g": None,
            "std_dev_g": None,
            "count": 0
        }

    sizes_sorted = sorted(sizes_g)
    n = Decimal(str(len(sizes_g)))

    # Promedio
    avg = sum(sizes_g) / n

    # Desviación estándar
    variance = sum((x - avg) ** 2 for x in sizes_g) / n
    std_dev = variance.sqrt()

    return {
        "min_g": float(sizes_sorted[0]),
        "max_g": float(sizes_sorted[-1]),
        "promedio_g": float(avg.quantize(Decimal("0.01"))),
        "std_dev_g": float(std_dev.quantize(Decimal("0.01"))),
        "count": len(sizes_g)
    }


def calculate_partial_harvest_impact(
        densidad_viva_antes: Decimal,
        densidad_retirada: Decimal,
        superficie_m2: Decimal
) -> Dict[str, Decimal]:
    """
    Impacto de cosecha parcial en densidad y organismos.

    Returns:
        densidad_viva_despues: org/m² después de la cosecha
        org_retirados: organismos cosechados
        org_remanentes: organismos que quedan
    """
    densidad_despues = (densidad_viva_antes - densidad_retirada).quantize(Decimal("0.0001"))
    if densidad_despues < Decimal("0"):
        densidad_despues = Decimal("0")

    org_retirados = (densidad_retirada * superficie_m2).quantize(Decimal("0.0001"))
    org_remanentes = (densidad_despues * superficie_m2).quantize(Decimal("0.0001"))

    return {
        "densidad_viva_despues": densidad_despues,
        "org_retirados": org_retirados,
        "org_remanentes": org_remanentes
    }


# ==================== COMPARATIVAS Y BENCHMARKS ====================

def calculate_cycle_comparison(
        ciclo_actual: Dict[str, Any],
        ciclo_anterior: Dict[str, Any],
        metricas: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Compara métricas entre dos ciclos.

    Args:
        ciclo_actual: {"pp_g": 15.5, "sob_pct": 85, "fcr": 1.3, ...}
        ciclo_anterior: {"pp_g": 14.2, "sob_pct": 82, "fcr": 1.4, ...}
        metricas: ["pp_g", "sob_pct", "fcr"]

    Returns:
        {"pp_g": {"actual": 15.5, "anterior": 14.2, "diff": 1.3, "diff_pct": 9.15}, ...}
    """
    result = {}

    for metric in metricas:
        actual = ciclo_actual.get(metric)
        anterior = ciclo_anterior.get(metric)

        if actual is None or anterior is None:
            result[metric] = {
                "actual": actual,
                "anterior": anterior,
                "diff": None,
                "diff_pct": None
            }
            continue

        actual_dec = Decimal(str(actual))
        anterior_dec = Decimal(str(anterior))

        diff = actual_dec - anterior_dec
        diff_pct = calculate_deviation_pct(actual_dec, anterior_dec)

        result[metric] = {
            "actual": float(actual_dec),
            "anterior": float(anterior_dec),
            "diff": float(diff.quantize(Decimal("0.01"))),
            "diff_pct": float(diff_pct) if diff_pct else None
        }

    return result


def calculate_percentile_rank(
        valor: Decimal,
        valores_historicos: List[Decimal]
) -> Optional[int]:
    """
    Percentil del valor respecto a históricos (0-100).

    Ejemplo: percentil 75 = mejor que el 75% de los ciclos históricos.
    """
    if not valores_historicos:
        return None

    menores = sum(1 for v in valores_historicos if v < valor)
    percentil = (Decimal(str(menores)) / Decimal(str(len(valores_historicos)))) * Decimal("100")

    return int(percentil.quantize(Decimal("1")))