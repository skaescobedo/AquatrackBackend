"""
Servicio de cálculos para métricas de acuacultura.

MEJORAS vs versión anterior:
- calculate_global_sob: reconstruye remanente pre-SOB correctamente
- calculate_weighted_pp: mini-fix para nulls (solo estanques con PP)
"""
from decimal import Decimal
from typing import List, Dict, Any, Optional


# ==================== CÁLCULOS BÁSICOS ====================

def calculate_densidad_viva(
    densidad_base: Decimal,
    densidad_retirada: Decimal,
    sob_pct: Decimal
) -> Decimal:
    """
    Calcula densidad viva actual.

    Fórmula:
    densidad_viva = (densidad_base - densidad_retirada) × (SOB% / 100)
    """
    densidad_remanente = densidad_base - densidad_retirada
    if densidad_remanente < Decimal("0"):
        densidad_remanente = Decimal("0")

    densidad_viva = densidad_remanente * (sob_pct / Decimal("100"))
    return densidad_viva.quantize(Decimal("0.0001"))


def calculate_org_vivos(densidad_viva: Decimal, superficie_m2: Decimal) -> Decimal:
    """
    Calcula organismos vivos totales en el estanque.

    Fórmula:
    org_vivos = densidad_viva × superficie
    """
    org_vivos = densidad_viva * superficie_m2
    return org_vivos.quantize(Decimal("0.0001"))


def calculate_biomasa_kg(org_vivos: Decimal, pp_g: Decimal) -> Decimal:
    """
    Calcula biomasa total en kg.

    Fórmula:
    biomasa_kg = org_vivos × (pp_g / 1000)
    """
    biomasa = org_vivos * (pp_g / Decimal("1000"))
    return biomasa.quantize(Decimal("0.1"))


# ==================== CÁLCULOS AGREGADOS ====================

def calculate_total_biomass(pond_snapshots: List[Dict[str, Any]]) -> Decimal:
    """Suma total de biomasa de todos los estanques."""
    total = Decimal("0")

    for snap in pond_snapshots:
        if snap.get("biomasa_est_kg") is not None:
            total += Decimal(str(snap["biomasa_est_kg"]))

    return total.quantize(Decimal("0.1"))


def calculate_weighted_density(pond_snapshots: List[Dict[str, Any]]) -> Optional[Decimal]:
    """
    Densidad promedio ponderada por superficie.

    Fórmula:
    densidad_prom = Σ(densidad_viva × superficie) / Σ(superficie)
    """
    dens_x_sup = Decimal("0")
    sup_total = Decimal("0")

    for snap in pond_snapshots:
        if (snap.get("densidad_viva_org_m2") is not None and
            snap.get("superficie_m2") is not None):

            dens = Decimal(str(snap["densidad_viva_org_m2"]))
            sup = Decimal(str(snap["superficie_m2"]))

            dens_x_sup += (dens * sup)
            sup_total += sup

    if sup_total > 0:
        return (dens_x_sup / sup_total).quantize(Decimal("0.0001"))

    return None


def calculate_global_sob(pond_snapshots: List[Dict[str, Any]]) -> Optional[Decimal]:
    """
    SOB global del ciclo.

    Fórmula CORRECTA:
    SOB% = (Σ organismos_vivos / Σ organismos_remanentes_pre_sob) × 100

    IMPORTANTE:
    - NO usar sob_vigente_pct en el denominador (sería circular)
    - Reconstruir el remanente PRE-SOB desde densidad_viva

    Razonamiento:
    - densidad_viva = densidad_remanente × (SOB% / 100)
    - Entonces: densidad_remanente = densidad_viva / (SOB% / 100)
    - organismos_remanentes = densidad_remanente × superficie

    MEJORA vs versión anterior:
    - Reconstruye correctamente el remanente pre-SOB
    - Evita usar SOB en ambos lados de la ecuación
    """
    total_vivos = Decimal("0")
    total_remanente_pre_sob = Decimal("0")

    for snap in pond_snapshots:
        # Vivos actuales
        if snap.get("org_vivos_est") is not None:
            total_vivos += Decimal(str(snap["org_vivos_est"]))

        # Remanente PRE-SOB (reconstruir desde densidad_viva)
        if (snap.get("densidad_viva_org_m2") is not None and
            snap.get("sob_vigente_pct") is not None and
            snap["sob_vigente_pct"] > 0 and
            snap.get("superficie_m2") is not None):

            dens_viva = Decimal(str(snap["densidad_viva_org_m2"]))
            sob_pct = Decimal(str(snap["sob_vigente_pct"]))
            sup = Decimal(str(snap["superficie_m2"]))

            # Revertir: densidad_remanente = densidad_viva / (SOB% / 100)
            dens_remanente = dens_viva / (sob_pct / Decimal("100"))
            org_remanente = dens_remanente * sup

            total_remanente_pre_sob += org_remanente

    if total_remanente_pre_sob > 0:
        sob_global = (total_vivos / total_remanente_pre_sob * Decimal("100"))
        return sob_global.quantize(Decimal("0.01"))

    return None


def calculate_weighted_pp(pond_snapshots: List[Dict[str, Any]]) -> Optional[Decimal]:
    """
    PP promedio ponderado por organismos vivos.

    Fórmula:
    pp_prom = Σ(pp × org_vivos) / Σ(org_vivos)

    MEJORA vs versión anterior (mini-fix):
    - Solo incluye estanques con pp_vigente_g != None
    - Evita dividir por 0
    - Evita promedios incorrectos cuando algunos estanques no tienen PP

    Ejemplo del problema que soluciona:
    - Estanque A: 10g, 1000 org → contribuye 10,000
    - Estanque B: None, 1000 org → NO contribuye (antes contribuía 0)
    - Antes: (10,000 + 0) / 2000 = 5g  ❌
    - Ahora: 10,000 / 1000 = 10g  ✅
    """
    pp_x_org = Decimal("0")
    org_total = Decimal("0")

    for snap in pond_snapshots:
        # Solo ponderar estanques que TIENEN pp_vigente_g
        if (snap.get("pp_vigente_g") is not None and
            snap.get("org_vivos_est") is not None):

            pp = Decimal(str(snap["pp_vigente_g"]))
            org = Decimal(str(snap["org_vivos_est"]))

            pp_x_org += (pp * org)
            org_total += org

    if org_total > 0:
        return (pp_x_org / org_total).quantize(Decimal("0.01"))

    return None


# ==================== DESVIACIONES Y TASAS ====================

def calculate_deviation_pct(
    actual: Decimal,
    proyectado: Decimal
) -> Optional[Decimal]:
    """
    Calcula desviación porcentual vs proyección.

    Fórmula:
    desviacion% = ((actual - proyectado) / proyectado) × 100
    """
    if proyectado == 0:
        return None

    desviacion = ((actual - proyectado) / proyectado * Decimal("100"))
    return desviacion.quantize(Decimal("0.01"))


def calculate_growth_rate(
    pp_final: Decimal,
    pp_inicial: Decimal,
    dias: int
) -> Optional[Decimal]:
    """
    Calcula tasa de crecimiento promedio (g/semana).

    Fórmula:
    tasa = (pp_final - pp_inicial) / (dias / 7)
    """
    if dias <= 0:
        return None

    semanas = Decimal(str(dias)) / Decimal("7")
    if semanas == 0:
        return None

    incremento = pp_final - pp_inicial
    tasa = incremento / semanas

    return tasa.quantize(Decimal("0.01"))


# ==================== VALIDACIONES ====================

def validate_positive_decimal(value: Any, field_name: str) -> Decimal:
    """Valida y convierte a Decimal positivo."""
    try:
        dec_value = Decimal(str(value))
        if dec_value < 0:
            raise ValueError(f"{field_name} debe ser positivo")
        return dec_value
    except (ValueError, TypeError, ArithmeticError) as e:
        raise ValueError(f"{field_name} inválido: {e}")


def validate_percentage(value: Any, field_name: str) -> Decimal:
    """Valida y convierte a porcentaje (0-100)."""
    dec_value = validate_positive_decimal(value, field_name)
    if dec_value > Decimal("100"):
        raise ValueError(f"{field_name} no puede ser mayor a 100%")
    return dec_value