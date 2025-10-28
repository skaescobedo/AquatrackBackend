from __future__ import annotations
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

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

    # Único plan por ciclo
    existing = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un plan de siembras para este ciclo")

    plan = SiembraPlan(
        ciclo_id=ciclo_id,
        ventana_inicio=payload.ventana_inicio,
        ventana_fin=payload.ventana_fin,
        densidad_org_m2=payload.densidad_org_m2,
        talla_inicial_g=payload.talla_inicial_g,
        status="p",
        observaciones=payload.observaciones,
        created_by=created_by_user_id
    )
    db.add(plan)
    db.flush()  # plan_id

    # Estanques vigentes de la granja
    ponds: list[Estanque] = (
        db.query(Estanque)
        .filter(Estanque.granja_id == farm.granja_id, Estanque.is_vigente.is_(True))
        .order_by(Estanque.estanque_id.asc())
        .all()
    )

    pond_ids = [p.estanque_id for p in ponds]
    total = len(pond_ids)
    siembras: list[SiembraEstanque] = []

    if total > 0:
        days = (payload.ventana_fin - payload.ventana_inicio).days
        # Distribución uniforme inclusiva
        for idx, pond_id in enumerate(pond_ids):
            if days <= 0:
                fecha_tentativa = payload.ventana_inicio
            else:
                step = round((days * idx) / max(1, total - 1))
                fecha_tentativa = payload.ventana_inicio + timedelta(days=step)

            siembras.append(
                SiembraEstanque(
                    siembra_plan_id=plan.siembra_plan_id,
                    estanque_id=pond_id,
                    status="p",
                    fecha_tentativa=fecha_tentativa,
                    created_by=created_by_user_id,
                )
            )

    if siembras:
        db.add_all(siembras)

    db.commit()
    db.refresh(plan)
    return plan

# =========================
# Obtener plan + items
# =========================

def get_plan_with_items_by_cycle(db: Session, ciclo_id: int) -> SiembraPlan:
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="El ciclo no tiene plan de siembras")
    return plan

# =========================
# Crear siembra manual para estanque
# =========================

def create_manual_seeding_for_pond(
    db: Session,
    siembra_plan_id: int,
    estanque_id: int,
    payload: SeedingCreateForPond,
    created_by_user_id: int | None,
) -> SiembraEstanque:
    plan = _get_plan(db, siembra_plan_id)
    cycle, farm = _get_cycle_and_farm(db, plan.ciclo_id)

    pond = db.get(Estanque, estanque_id)
    if not pond or pond.granja_id != farm.granja_id:
        raise HTTPException(status_code=404, detail="Estanque no encontrado en la granja del ciclo")

    if not pond.is_vigente:
        raise HTTPException(status_code=409, detail="Solo se permiten siembras en estanques con is_vigente=1")

    existing = (
        db.query(SiembraEstanque)
        .filter(and_(
            SiembraEstanque.siembra_plan_id == siembra_plan_id,
            SiembraEstanque.estanque_id == estanque_id
        ))
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ese estanque ya tiene una siembra en el plan")

    seeding = SiembraEstanque(
        siembra_plan_id=siembra_plan_id,
        estanque_id=estanque_id,
        status="p",
        fecha_tentativa=payload.fecha_tentativa,
        lote=payload.lote,
        densidad_override_org_m2=payload.densidad_override_org_m2,
        talla_inicial_override_g=payload.talla_inicial_override_g,
        observaciones=payload.observaciones,
        created_by=created_by_user_id
    )
    db.add(seeding)
    db.commit()
    db.refresh(seeding)
    return seeding

# =========================
# Reprogramar siembra (fecha/densidad/talla/lote)
# =========================

def _dec(value) -> Decimal:
    return Decimal(str(value))

def reprogram_seeding(
    db: Session,
    siembra_estanque_id: int,
    payload: SeedingReprogramIn,
    changed_by_user_id: int,
) -> SiembraEstanque:
    seeding = db.get(SiembraEstanque, siembra_estanque_id)
    if not seeding:
        raise HTTPException(status_code=404, detail="Siembra de estanque no encontrada")

    if seeding.status == "f":
        raise HTTPException(status_code=409, detail="No se puede reprogramar una siembra ya confirmada")

    # Fecha (None = no cambia; válida = actualiza y loguea)
    if payload.fecha_nueva is not None:
        fecha_anterior = seeding.fecha_tentativa
        if fecha_anterior != payload.fecha_nueva:
            seeding.fecha_tentativa = payload.fecha_nueva
            db.add(SiembraFechaLog(
                siembra_estanque_id=seeding.siembra_estanque_id,
                fecha_anterior=fecha_anterior,
                fecha_nueva=payload.fecha_nueva,
                motivo=payload.motivo,
                changed_by=changed_by_user_id,
            ))

    # Densidad (None o 0 = no cambia; otro => actualiza)
    if payload.densidad_override_org_m2 is not None:
        try:
            if _dec(payload.densidad_override_org_m2) != Decimal("0"):
                seeding.densidad_override_org_m2 = _dec(payload.densidad_override_org_m2)
        except Exception:
            pass

    # Talla (None o 0 = no cambia; otro => actualiza)
    if payload.talla_inicial_override_g is not None:
        try:
            if _dec(payload.talla_inicial_override_g) != Decimal("0"):
                seeding.talla_inicial_override_g = _dec(payload.talla_inicial_override_g)
        except Exception:
            pass

    # Lote (None = no cambia; string => asigna, vacía = limpia)
    if payload.lote is not None:
        seeding.lote = payload.lote

    db.add(seeding)
    db.commit()
    db.refresh(seeding)
    return seeding

# =========================
# Confirmar siembra
# =========================

def confirm_seeding(
    db: Session,
    siembra_estanque_id: int,
    confirmed_by_user_id: int | None
) -> SiembraEstanque:
    seeding = _get_seeding(db, siembra_estanque_id)

    if seeding.status == "f":
        return seeding  # idempotente

    seeding.status = "f"
    seeding.fecha_siembra = today_mazatlan()

    # Activar estanque
    pond = db.get(Estanque, seeding.estanque_id)
    if pond:
        pond.status = "a"
        db.add(pond)

    # Plan pasa a 'e' si estaba 'p'
    plan = db.get(SiembraPlan, seeding.siembra_plan_id)
    if plan and plan.status == "p":
        plan.status = "e"
        db.add(plan)

    db.add(seeding)
    db.commit()
    db.refresh(seeding)
    return seeding

# =========================
# Eliminar plan (si nada confirmado)
# =========================

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

    db.query(SiembraEstanque).filter(SiembraEstanque.siembra_plan_id == siembra_plan_id).delete(synchronize_session=False)
    db.delete(plan)
    db.commit()