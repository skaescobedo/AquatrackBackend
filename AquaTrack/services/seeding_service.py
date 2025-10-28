from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.cycle import Ciclo
from models.farm import Granja
from models.pond import Estanque
from models.seeding import SiembraPlan, SiembraEstanque, SiembraFechaLog
from schemas.seeding import (
    SeedingPlanCreate, SeedingPlanOut, SeedingPlanDetailOut,
    SeedingPondCreate, SeedingPondOut
)


# --- helpers ---
def _ensure_cycle_and_farm(db: Session, ciclo_id: int) -> tuple[Ciclo, Granja]:
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle or cycle.status != "a":
        raise HTTPException(status_code=404, detail="Ciclo no encontrado o no activo")
    farm = db.get(Granja, cycle.granja_id)
    if not farm or not farm.is_active:
        raise HTTPException(status_code=409, detail="La granja del ciclo no existe o está inactiva")
    return cycle, farm


def _spread_dates(ventana_inicio: date, ventana_fin: date, n: int) -> list[date | None]:
    if n <= 0:
        return []
    if ventana_fin < ventana_inicio:
        raise HTTPException(status_code=400, detail="ventana_fin no puede ser menor a ventana_inicio")
    days = (ventana_fin - ventana_inicio).days + 1
    if days <= 0:
        days = 1
    # distribución simple: secuencial (round-robin) dentro de la ventana
    result: list[date] = []
    for i in range(n):
        offset = (i % days)
        result.append(ventana_inicio + timedelta(days=offset))
    return result


def _ponds_without_plan_entries(db: Session, ciclo_id: int, plan_id: int, farm_id: int) -> list[Estanque]:
    # Estanques vigentes (is_vigente=1) de la granja del ciclo,
    # que NO tengan ya una siembra_estanque para este plan
    sub = db.query(SiembraEstanque.estanque_id).filter(SiembraEstanque.siembra_plan_id == plan_id)
    ponds = (
        db.query(Estanque)
        .filter(
            Estanque.granja_id == farm_id,
            Estanque.is_vigente.is_(True),
            ~Estanque.estanque_id.in_(sub.subquery()),
        )
        .order_by(Estanque.estanque_id.asc())
        .all()
    )
    return ponds


# --- service API ---
def create_plan_with_autofill(
    db: Session,
    ciclo_id: int,
    payload: SeedingPlanCreate,
    current_user_id: int,
) -> SiembraPlan:
    cycle, farm = _ensure_cycle_and_farm(db, ciclo_id)

    # Validaciones básicas de ventanas ya las refuerza el esquema SQL; aquí prevenimos pronto
    if payload.ventana_fin < payload.ventana_inicio:
        raise HTTPException(status_code=400, detail="ventana_inicio debe ser <= ventana_fin")

    plan = SiembraPlan(
        ciclo_id=ciclo_id,
        ventana_inicio=payload.ventana_inicio,
        ventana_fin=payload.ventana_fin,
        densidad_org_m2=payload.densidad_org_m2,
        talla_inicial_g=payload.talla_inicial_g,
        status="p",
        observaciones=payload.observaciones,
        created_by=current_user_id,
    )
    db.add(plan)
    db.flush()  # siembra_plan_id

    try:
        if payload.autofill:
            ponds = _ponds_without_plan_entries(db, ciclo_id, plan.siembra_plan_id, farm.granja_id)
            fechas = _spread_dates(payload.ventana_inicio, payload.ventana_fin, len(ponds))

            siembras: list[SiembraEstanque] = []
            for pond, f in zip(ponds, fechas, strict=True):
                if not pond.is_vigente:
                    continue  # doble seguro
                siembras.append(SiembraEstanque(
                    siembra_plan_id=plan.siembra_plan_id,
                    estanque_id=pond.estanque_id,
                    status="p",
                    fecha_tentativa=f,
                    created_by=current_user_id,
                ))
                # regla de negocio: al crear siembra_estanque, el estanque pasa a 'a' (activo)
                pond.status = "a"
                db.add(pond)

            if siembras:
                db.add_all(siembras)

        db.commit()
        db.refresh(plan)
        return plan
    except Exception:
        db.rollback()
        raise


def get_plan_detail(db: Session, siembra_plan_id: int) -> SiembraPlan:
    plan = db.get(SiembraPlan, siembra_plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan de siembra no encontrado")
    return plan


def create_manual_seeding_for_pond(
    db: Session,
    siembra_plan_id: int,
    estanque_id: int,
    data: SeedingPondCreate,
    current_user_id: int,
) -> SiembraEstanque:
    plan = get_plan_detail(db, siembra_plan_id)
    cycle = db.get(Ciclo, plan.ciclo_id)
    farm = db.get(Granja, cycle.granja_id)

    pond = db.get(Estanque, estanque_id)
    if not pond or pond.granja_id != farm.granja_id:
        raise HTTPException(status_code=404, detail="Estanque no encontrado en la granja del ciclo")
    if not pond.is_vigente:
        raise HTTPException(status_code=409, detail="El estanque no está vigente (no se permiten nuevas siembras)")

    # Evitar duplicado por clave única (plan, estanque)
    existing = db.query(SiembraEstanque).filter(
        and_(SiembraEstanque.siembra_plan_id == siembra_plan_id, SiembraEstanque.estanque_id == estanque_id)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe una siembra para este estanque en el plan")

    se = SiembraEstanque(
        siembra_plan_id=siembra_plan_id,
        estanque_id=estanque_id,
        status="p",
        fecha_tentativa=data.fecha_tentativa,
        lote=data.lote,
        densidad_override_org_m2=data.densidad_override_org_m2,
        talla_inicial_override_g=data.talla_inicial_override_g,
        observaciones=data.observaciones,
        created_by=current_user_id,
    )
    # Activar estanque al crear la siembra
    pond.status = "a"

    try:
        db.add(se)
        db.add(pond)
        db.commit()
        db.refresh(se)
        return se
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflicto de unicidad en siembra_estanque")
    except Exception:
        db.rollback()
        raise


def list_seedings_of_plan(db: Session, siembra_plan_id: int) -> list[SiembraEstanque]:
    _ = get_plan_detail(db, siembra_plan_id)
    return (
        db.query(SiembraEstanque)
        .filter(SiembraEstanque.siembra_plan_id == siembra_plan_id)
        .order_by(SiembraEstanque.siembra_estanque_id.asc())  # noqa: E241 (espacio forzado por formatter)
        .all()
    )


def reprogram_seeding_date(
    db: Session,
    siembra_estanque_id: int,
    fecha_nueva: date,
    motivo: str | None,
    current_user_id: int,
) -> SiembraEstanque:
    se = db.get(SiembraEstanque, siembra_estanque_id)
    if not se:
        raise HTTPException(status_code=404, detail="Siembra_estanque no encontrada")

    # Bitácora (tentativa → nueva)
    log = SiembraFechaLog(
        siembra_estanque_id=se.siembra_estanque_id,
        fecha_anterior=se.fecha_tentativa,
        fecha_nueva=fecha_nueva,
        motivo=motivo,
        changed_by=current_user_id,
    )
    se.fecha_tentativa = fecha_nueva

    try:
        db.add(se)
        db.add(log)
        db.commit()
        db.refresh(se)
        return se
    except Exception:
        db.rollback()
        raise
