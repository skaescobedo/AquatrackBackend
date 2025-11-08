# services/seeding_service.py
"""
Servicio de gestión de siembras.

FIX IMPORTANTE:
- ciclo.fecha_inicio ahora se actualiza con la fecha de la ÚLTIMA siembra confirmada
  (no la primera, para reflejar el verdadero inicio operativo del ciclo)
"""
from __future__ import annotations
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, asc, desc

from utils.datetime_utils import today_mazatlan
from models.cycle import Ciclo
from models.farm import Granja
from models.pond import Estanque
from models.seeding import SiembraPlan, SiembraEstanque, SiembraFechaLog
from schemas.seeding import (
    SeedingPlanCreate, SeedingCreateForPond, SeedingReprogramIn
)


# =========================
# Helpers de validación
# =========================

def _get_cycle_and_farm(db: Session, ciclo_id: int) -> tuple[Ciclo, Granja]:
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    farm = db.get(Granja, cycle.granja_id)
    if not farm or not farm.is_active:
        raise HTTPException(status_code=409, detail="La granja del ciclo no existe o está inactiva")
    return cycle, farm


def _get_plan(db: Session, siembra_plan_id: int) -> SiembraPlan:
    plan = db.get(SiembraPlan, siembra_plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan de siembras no encontrado")
    return plan


def _get_seeding(db: Session, siembra_estanque_id: int) -> SiembraEstanque:
    seeding = db.get(SiembraEstanque, siembra_estanque_id)
    if not seeding:
        raise HTTPException(status_code=404, detail="Siembra de estanque no encontrada")
    return seeding


def _ensure_window(payload: SeedingPlanCreate):
    if payload.ventana_inicio > payload.ventana_fin:
        raise HTTPException(status_code=400, detail="ventana_inicio no puede ser mayor a ventana_fin")


# =========================
# Crear Plan + auto-seedings
# =========================

def create_plan_and_autoseed(
        db: Session,
        ciclo_id: int,
        payload: SeedingPlanCreate,
        created_by_user_id: int | None,
) -> SiembraPlan:
    cycle, farm = _get_cycle_and_farm(db, ciclo_id)
    _ensure_window(payload)

    dias_anticipacion = (cycle.fecha_inicio - payload.ventana_inicio).days
    if dias_anticipacion > 30:
        raise HTTPException(
            status_code=400,
            detail=f"La ventana de inicio ({payload.ventana_inicio}) está {dias_anticipacion} días antes del inicio del ciclo. Máximo permitido: 30 días de anticipación."
        )

    existing = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un plan de siembras para este ciclo (plan_id={existing.siembra_plan_id})"
        )

    plan = SiembraPlan(
        ciclo_id=ciclo_id,
        ventana_inicio=payload.ventana_inicio,
        ventana_fin=payload.ventana_fin,
        densidad_org_m2=payload.densidad_org_m2,
        talla_inicial_g=payload.talla_inicial_g,
        status='p',
        observaciones=payload.observaciones,
        created_by=created_by_user_id
    )
    db.add(plan)
    db.flush()

    ponds = db.query(Estanque).filter(
        and_(Estanque.granja_id == farm.granja_id, Estanque.is_vigente == True)
    ).all()

    if not ponds:
        raise HTTPException(status_code=400, detail="No hay estanques vigentes en la granja")

    dates = _distribute_dates_evenly(payload.ventana_inicio, payload.ventana_fin, len(ponds))

    for pond, fecha_tent in zip(ponds, dates):
        se = SiembraEstanque(
            siembra_plan_id=plan.siembra_plan_id,
            estanque_id=pond.estanque_id,
            status='p',
            fecha_tentativa=fecha_tent,
            densidad_override_org_m2=None,
            talla_inicial_override_g=None,
            created_by=created_by_user_id
        )
        db.add(se)

    db.commit()
    db.refresh(plan)
    return plan


def _distribute_dates_evenly(start, end, n: int):
    if n <= 1:
        return [start]
    days = (end - start).days
    if days < 0:
        return [start]
    return [start + timedelta(days=round((days * i) / max(1, n - 1))) for i in range(n)]


def get_plan_with_items_by_cycle(db: Session, ciclo_id: int):
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        return None

    lines = (
        db.query(SiembraEstanque, Estanque.nombre)
        .join(Estanque, SiembraEstanque.estanque_id == Estanque.estanque_id)
        .filter(SiembraEstanque.siembra_plan_id == plan.siembra_plan_id)
        .order_by(asc(SiembraEstanque.fecha_tentativa))
        .all()
    )

    items = []
    for se, pond_name in lines:
        dens = se.densidad_override_org_m2 if se.densidad_override_org_m2 else plan.densidad_org_m2
        talla = se.talla_inicial_override_g if se.talla_inicial_override_g else plan.talla_inicial_g

        items.append({
            "siembra_estanque_id": se.siembra_estanque_id,
            "estanque_id": se.estanque_id,
            "estanque_nombre": pond_name,
            "status": se.status,
            "fecha_tentativa": se.fecha_tentativa,
            "fecha_siembra": se.fecha_siembra,
            "lote": se.lote,
            "densidad_org_m2": float(dens) if dens else None,
            "talla_inicial_g": float(talla) if talla else None,
            "observaciones": se.observaciones,
            "created_at": se.created_at,
            "updated_at": se.updated_at
        })

    return {
        "siembra_plan_id": plan.siembra_plan_id,
        "ciclo_id": plan.ciclo_id,
        "ventana_inicio": plan.ventana_inicio,
        "ventana_fin": plan.ventana_fin,
        "densidad_org_m2": float(plan.densidad_org_m2) if plan.densidad_org_m2 else None,
        "talla_inicial_g": float(plan.talla_inicial_g) if plan.talla_inicial_g else None,
        "status": plan.status,
        "observaciones": plan.observaciones,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "items": items
    }


def create_manual_seeding_for_pond(
        db: Session,
        siembra_plan_id: int,
        estanque_id: int,
        payload: SeedingCreateForPond,
        created_by_user_id: int | None
) -> SiembraEstanque:
    plan = _get_plan(db, siembra_plan_id)

    pond = db.get(Estanque, estanque_id)
    if not pond:
        raise HTTPException(status_code=404, detail="Estanque no encontrado")

    existing = db.query(SiembraEstanque).filter(
        and_(
            SiembraEstanque.siembra_plan_id == siembra_plan_id,
            SiembraEstanque.estanque_id == estanque_id
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una siembra para este estanque en el plan (siembra_estanque_id={existing.siembra_estanque_id})"
        )

    se = SiembraEstanque(
        siembra_plan_id=siembra_plan_id,
        estanque_id=estanque_id,
        status='p',
        fecha_tentativa=payload.fecha_tentativa,
        lote=payload.lote,
        densidad_override_org_m2=payload.densidad_org_m2,
        talla_inicial_override_g=payload.talla_inicial_g,
        observaciones=payload.observaciones,
        created_by=created_by_user_id
    )
    db.add(se)
    db.commit()
    db.refresh(se)
    return se


def reprogram_seeding(
        db: Session,
        siembra_estanque_id: int,
        payload: SeedingReprogramIn,
        reprogrammed_by_user_id: int | None
) -> SiembraEstanque:
    seeding = _get_seeding(db, siembra_estanque_id)

    if seeding.status == "f":
        raise HTTPException(
            status_code=400,
            detail="No se puede reprogramar una siembra ya confirmada"
        )

    fecha_cambio = False
    if payload.fecha_nueva is not None:
        if seeding.fecha_tentativa != payload.fecha_nueva:
            log = SiembraFechaLog(
                siembra_estanque_id=siembra_estanque_id,
                fecha_anterior=seeding.fecha_tentativa,
                fecha_nueva=payload.fecha_nueva,
                motivo=payload.motivo or "Sin motivo especificado",
                changed_by=reprogrammed_by_user_id
            )
            db.add(log)
            seeding.fecha_tentativa = payload.fecha_nueva
            fecha_cambio = True

    if payload.lote is not None:
        seeding.lote = payload.lote

    if payload.densidad_override_org_m2 is not None and payload.densidad_override_org_m2 > 0:
        seeding.densidad_override_org_m2 = payload.densidad_override_org_m2

    if payload.talla_inicial_override_g is not None and payload.talla_inicial_override_g > 0:
        seeding.talla_inicial_override_g = payload.talla_inicial_override_g

    db.add(seeding)
    db.commit()
    db.refresh(seeding)
    return seeding


def confirm_seeding(
        db: Session,
        siembra_estanque_id: int,
        confirmed_by_user_id: int | None
) -> SiembraEstanque:
    seeding = _get_seeding(db, siembra_estanque_id)

    if seeding.status == "f":
        return seeding

    seeding.status = "f"
    seeding.fecha_siembra = today_mazatlan()

    pond = db.get(Estanque, seeding.estanque_id)
    if pond:
        pond.status = "a"
        db.add(pond)

    plan = db.get(SiembraPlan, seeding.siembra_plan_id)
    if plan and plan.status == "p":
        plan.status = "e"
        db.add(plan)

    db.add(seeding)
    db.commit()
    db.refresh(seeding)

    plan_finalized = _check_and_finalize_plan(db, seeding.siembra_plan_id)

    if plan_finalized:
        _update_plan_windows(db, seeding.siembra_plan_id)
        _sync_cycle_fecha_inicio(db, seeding.siembra_plan_id)

    return seeding


def _check_and_finalize_plan(db: Session, siembra_plan_id: int) -> bool:
    plan = db.get(SiembraPlan, siembra_plan_id)
    if not plan or plan.status == "f":
        return False

    total = db.query(func.count(SiembraEstanque.siembra_estanque_id)).filter(
        SiembraEstanque.siembra_plan_id == siembra_plan_id
    ).scalar() or 0

    confirmadas = db.query(func.count(SiembraEstanque.siembra_estanque_id)).filter(
        SiembraEstanque.siembra_plan_id == siembra_plan_id,
        SiembraEstanque.status == "f"
    ).scalar() or 0

    if total > 0 and confirmadas == total:
        plan.status = "f"
        db.add(plan)
        db.commit()
        return True

    return False


def _update_plan_windows(db: Session, siembra_plan_id: int) -> None:
    """Actualiza ventanas del plan con fechas reales de siembra."""
    plan = db.get(SiembraPlan, siembra_plan_id)
    if not plan:
        return

    siembras_confirmadas = (
        db.query(SiembraEstanque)
        .filter(
            SiembraEstanque.siembra_plan_id == siembra_plan_id,
            SiembraEstanque.status == "f",
            SiembraEstanque.fecha_siembra.isnot(None)
        )
        .order_by(asc(SiembraEstanque.fecha_siembra))
        .all()
    )

    if siembras_confirmadas:
        plan.ventana_inicio = siembras_confirmadas[0].fecha_siembra
        plan.ventana_fin = siembras_confirmadas[-1].fecha_siembra
        db.add(plan)
        db.commit()


def _sync_cycle_fecha_inicio(db: Session, siembra_plan_id: int) -> None:
    """
    CAMBIO CRÍTICO: Sincroniza ciclo.fecha_inicio con fecha de ÚLTIMA siembra confirmada.

    Al confirmar la última siembra:
    1. Obtiene fecha de ÚLTIMA siembra confirmada (no primera)
    2. Actualiza ciclo.fecha_inicio con esa fecha
    3. Esto asegura que el ciclo comienza cuando TODOS los estanques están sembrados

    Resultado:
    - ciclo.fecha_inicio = fecha de último estanque sembrado
    - Analytics calcula edad correcta desde el inicio real del ciclo completo
    - Proyecciones alineadas con la realidad operativa
    """
    plan = db.get(SiembraPlan, siembra_plan_id)
    if not plan:
        return

    # CAMBIO: Ordenar DESC para obtener la ÚLTIMA siembra (no la primera)
    ultima_siembra = (
        db.query(SiembraEstanque)
        .filter(
            SiembraEstanque.siembra_plan_id == siembra_plan_id,
            SiembraEstanque.status == "f",
            SiembraEstanque.fecha_siembra.isnot(None)
        )
        .order_by(desc(SiembraEstanque.fecha_siembra))  # ← DESC para última
        .first()
    )

    if not ultima_siembra:
        return

    ciclo = db.get(Ciclo, plan.ciclo_id)
    if not ciclo:
        return

    fecha_anterior = ciclo.fecha_inicio
    fecha_nueva = ultima_siembra.fecha_siembra

    if fecha_anterior != fecha_nueva:
        ciclo.fecha_inicio = fecha_nueva
        db.add(ciclo)
        db.commit()
        print(f"✅ ciclo.fecha_inicio actualizado: {fecha_anterior} → {fecha_nueva} (última siembra)")


def get_plan_status(db: Session, siembra_plan_id: int) -> dict:
    plan = db.get(SiembraPlan, siembra_plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    total = db.query(func.count(SiembraEstanque.siembra_estanque_id)).filter(
        SiembraEstanque.siembra_plan_id == siembra_plan_id
    ).scalar() or 0

    confirmadas = db.query(func.count(SiembraEstanque.siembra_estanque_id)).filter(
        SiembraEstanque.siembra_plan_id == siembra_plan_id,
        SiembraEstanque.status == "f"
    ).scalar() or 0

    return {
        "plan_status": plan.status,
        "total_siembras": total,
        "confirmadas": confirmadas,
        "pendientes": total - confirmadas,
        "all_confirmed": confirmadas == total and total > 0
    }


def delete_plan_if_no_confirmed(db: Session, siembra_plan_id: int) -> None:
    plan = _get_plan(db, siembra_plan_id)

    confirmed_exists = (
        db.query(func.count(SiembraEstanque.siembra_estanque_id))
        .filter(and_(
            SiembraEstanque.siembra_plan_id == siembra_plan_id,
            SiembraEstanque.status == "f"
        )).scalar()
    )
    if confirmed_exists and int(confirmed_exists) > 0:
        raise HTTPException(status_code=409, detail="No se puede eliminar: existen siembras confirmadas")

    db.query(SiembraEstanque).filter(SiembraEstanque.siembra_plan_id == siembra_plan_id).delete(
        synchronize_session=False)
    db.delete(plan)
    db.commit()


def get_seeding_logs(db: Session, siembra_estanque_id: int):
    logs = (
        db.query(SiembraFechaLog)
        .filter(SiembraFechaLog.siembra_estanque_id == siembra_estanque_id)
        .order_by(desc(SiembraFechaLog.changed_at))
        .all()
    )
    return logs