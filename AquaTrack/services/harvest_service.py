from __future__ import annotations
from datetime import timedelta, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from fastapi import HTTPException, status

from utils.datetime_utils import today_mazatlan, now_mazatlan
from models.cycle import Ciclo
from models.farm import Granja
from models.pond import Estanque
from models.seeding import SiembraPlan, SiembraEstanque
from models.harvest import CosechaOla, CosechaEstanque, CosechaFechaLog
from models.biometria import Biometria
from schemas.harvest import HarvestWaveCreate, HarvestReprogramIn, HarvestConfirmIn


def _get_cycle_and_farm(db: Session, ciclo_id: int) -> tuple[Ciclo, Granja]:
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    farm = db.get(Granja, cycle.granja_id)
    if not farm or not farm.is_active:
        raise HTTPException(status_code=409, detail="La granja del ciclo no existe o está inactiva")
    return cycle, farm


def _next_order(db: Session, ciclo_id: int) -> int:
    current_max = db.query(func.max(CosechaOla.orden)).filter(CosechaOla.ciclo_id == ciclo_id).scalar()
    return int(current_max or 0) + 1


def _pond_ids_for_cycle(db: Session, ciclo_id: int, granja_id: int) -> list[int]:
    """
    Regla: si hay estanques vinculados al plan de siembra del ciclo (siembra_estanque),
    usarlos TODOS (status p o f). Si no hay ninguno, usar estanques vigentes de la granja.
    """
    # 1) Estanques planificados para el ciclo (sin exigir confirmación)
    planned = (
        db.query(Estanque.estanque_id)
        .join(SiembraEstanque, SiembraEstanque.estanque_id == Estanque.estanque_id)
        .join(SiembraPlan, SiembraPlan.siembra_plan_id == SiembraEstanque.siembra_plan_id)
        .filter(
            SiembraPlan.ciclo_id == ciclo_id,
            Estanque.granja_id == granja_id,
        )
        .order_by(Estanque.estanque_id.asc())
        .all()
    )
    ids = [eid for (eid,) in planned]
    if ids:
        return ids

    # 2) Fallback: todos los estanques vigentes de la granja
    fallback = (
        db.query(Estanque.estanque_id)
        .filter(
            Estanque.granja_id == granja_id,
            Estanque.is_vigente == 1,
        )
        .order_by(Estanque.estanque_id.asc())
        .all()
    )
    return [eid for (eid,) in fallback]


def create_wave_and_autolines(
        db: Session,
        ciclo_id: int,
        payload: HarvestWaveCreate,
        created_by_user_id: int | None,
) -> CosechaOla:
    cycle, farm = _get_cycle_and_farm(db, ciclo_id)

    ola = CosechaOla(
        ciclo_id=ciclo_id,
        nombre=payload.nombre,
        tipo=payload.tipo,
        ventana_inicio=payload.ventana_inicio,
        ventana_fin=payload.ventana_fin,
        objetivo_retiro_org_m2=payload.objetivo_retiro_org_m2,
        status="p",
        orden=payload.orden if payload.orden is not None else _next_order(db, ciclo_id),
        notas=payload.notas,
        created_by=created_by_user_id
    )
    db.add(ola)
    db.flush()

    pond_ids = _pond_ids_for_cycle(db, ciclo_id, farm.granja_id)

    cosechas: list[CosechaEstanque] = []
    total = len(pond_ids)
    if total > 0:
        days = (payload.ventana_fin - payload.ventana_inicio).days
        for idx, pond_id in enumerate(pond_ids):
            if days <= 0:
                fecha = payload.ventana_inicio
            else:
                step = round((days * idx) / max(1, total - 1))
                fecha = payload.ventana_inicio + timedelta(days=step)

            cosechas.append(
                CosechaEstanque(
                    estanque_id=pond_id,
                    cosecha_ola_id=ola.cosecha_ola_id,
                    status="p",
                    fecha_cosecha=fecha,
                    created_by=created_by_user_id
                )
            )

    if cosechas:
        db.add_all(cosechas)

    db.commit()
    db.refresh(ola)
    return ola


def list_waves(db: Session, ciclo_id: int) -> list[CosechaOla]:
    _get_cycle_and_farm(db, ciclo_id)  # valida que exista
    return (
        db.query(CosechaOla)
        .filter(CosechaOla.ciclo_id == ciclo_id)
        .order_by(CosechaOla.orden.asc(), CosechaOla.created_at.asc())
        .all()
    )


def get_wave_with_items(db: Session, cosecha_ola_id: int) -> CosechaOla:
    ola = db.get(CosechaOla, cosecha_ola_id)
    if not ola:
        raise HTTPException(status_code=404, detail="Ola no encontrada")
    # Acceso perezoso: al serializar, FastAPI/ORM resolverá las cosechas
    return ola


def reprogram_line_date(
        db: Session,
        cosecha_estanque_id: int,
        payload: HarvestReprogramIn,
        changed_by_user_id: int,
) -> CosechaEstanque:
    """
    Reprograma la fecha de una línea de cosecha.
    Si la ola estaba en 'p' (planeado), la marca como 'r' (reprogramada).
    """
    line = db.get(CosechaEstanque, cosecha_estanque_id)
    if not line:
        raise HTTPException(status_code=404, detail="cosecha_estanque no encontrada")

    if line.status == "c":
        raise HTTPException(status_code=409, detail="No se puede reprogramar una cosecha confirmada")

    if line.fecha_cosecha != payload.fecha_nueva:
        # Registrar log de cambio
        db.add(CosechaFechaLog(
            cosecha_estanque_id=line.cosecha_estanque_id,
            fecha_anterior=line.fecha_cosecha,
            fecha_nueva=payload.fecha_nueva,
            motivo=payload.motivo,
            changed_by=changed_by_user_id,
        ))
        line.fecha_cosecha = payload.fecha_nueva

        # Marcar ola como reprogramada si estaba planeada
        ola = db.get(CosechaOla, line.cosecha_ola_id)
        if ola and ola.status == "p":
            ola.status = "r"
            db.add(ola)

    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _get_latest_pp_for_pond_in_cycle(db: Session, ciclo_id: int, estanque_id: int) -> Decimal:
    bio = (
        db.query(Biometria)
        .filter(Biometria.ciclo_id == ciclo_id, Biometria.estanque_id == estanque_id)
        .order_by(desc(Biometria.fecha), desc(Biometria.created_at))
        .first()
    )
    if not bio:
        raise HTTPException(
            status_code=409,
            detail="No hay biometrías para este estanque en el ciclo; no se puede confirmar sin PP vigente"
        )
    try:
        return Decimal(str(bio.pp_g))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="PP inválido en la última biometría")


def confirm_line(
        db: Session,
        cosecha_estanque_id: int,
        payload: HarvestConfirmIn,
        confirmed_by_user_id: int,
) -> CosechaEstanque:
    line = db.get(CosechaEstanque, cosecha_estanque_id)
    if not line:
        raise HTTPException(status_code=404, detail="cosecha_estanque no encontrada")

    if line.status == "c":
        return line  # idempotente

    # Datos para derivaciones
    ola = db.get(CosechaOla, line.cosecha_ola_id)
    if not ola:
        raise HTTPException(status_code=404, detail="Ola asociada no encontrada")

    pp_g = _get_latest_pp_for_pond_in_cycle(db, ola.ciclo_id, line.estanque_id)  # Decimal
    pond = db.get(Estanque, line.estanque_id)
    if not pond:
        raise HTTPException(status_code=404, detail="Estanque no encontrado")

    try:
        area_m2 = Decimal(str(pond.superficie_m2))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="superficie_m2 inválida en estanque")

    # Normaliza entradas
    biomasa_kg = Decimal(str(payload.biomasa_kg)) if payload.biomasa_kg is not None else None
    densidad = Decimal(str(payload.densidad_retirada_org_m2)) if payload.densidad_retirada_org_m2 is not None else None

    # Derivar faltante
    if densidad is None and biomasa_kg is None:
        raise HTTPException(status_code=422, detail="Se requiere biomasa_kg o densidad_retirada_org_m2")

    if densidad is None:
        # densidad = (biomasa_kg * 1000 / pp_g) / area_m2
        if pp_g <= 0 or area_m2 <= 0:
            raise HTTPException(status_code=422, detail="No se puede derivar densidad (PP o área no válidos)")
        densidad = (biomasa_kg * Decimal("1000")) / pp_g / area_m2

    if biomasa_kg is None:
        # biomasa = (densidad * area * pp_g) / 1000
        if area_m2 <= 0:
            raise HTTPException(status_code=422, detail="Área del estanque inválida")
        biomasa_kg = (densidad * area_m2 * pp_g) / Decimal("1000")

    # Persistir confirmación
    line.status = "c"
    line.pp_g = pp_g  # guarda PP vigente
    line.biomasa_kg = biomasa_kg
    line.densidad_retirada_org_m2 = densidad
    if payload.notas is not None:
        line.notas = payload.notas
    line.confirmado_por = confirmed_by_user_id
    line.confirmado_event_at = now_mazatlan()

    db.add(line)
    db.commit()
    db.refresh(line)
    return line


# =============== NUEVO: Cancelación masiva de ola =================

def cancel_wave(db: Session, cosecha_ola_id: int) -> dict:
    """
    Cancela una ola completa:
    - Marca la ola con status='x'
    - Cancela todas las líneas de cosecha pendientes (status='p')
    - NO toca las líneas ya confirmadas (status='c')

    Returns:
        dict con conteo de líneas canceladas
    """
    ola = db.get(CosechaOla, cosecha_ola_id)
    if not ola:
        raise HTTPException(status_code=404, detail="Ola no encontrada")

    # Validar que no esté ya cancelada
    if ola.status == "x":
        raise HTTPException(status_code=409, detail="La ola ya está cancelada")

    # Marcar ola como cancelada
    ola.status = "x"
    db.add(ola)

    # Cancelar solo líneas pendientes (no confirmadas)
    lines_to_cancel = (
        db.query(CosechaEstanque)
        .filter(
            CosechaEstanque.cosecha_ola_id == cosecha_ola_id,
            CosechaEstanque.status == "p"
        )
        .all()
    )

    count = 0
    for line in lines_to_cancel:
        line.status = "x"
        db.add(line)
        count += 1

    db.commit()

    return {
        "cosecha_ola_id": cosecha_ola_id,
        "ola_cancelada": True,
        "lineas_canceladas": count,
        "mensaje": f"Ola cancelada. {count} líneas pendientes marcadas como canceladas."
    }