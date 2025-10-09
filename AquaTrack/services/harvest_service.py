from __future__ import annotations
from datetime import date, timedelta, datetime, timezone
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, asc
from models.ciclo import Ciclo
from models.estanque import Estanque
from models.plan_cosechas import PlanCosechas
from models.cosecha_ola import CosechaOla
from models.cosecha_estanque import CosechaEstanque
from models.cosecha_fecha_log import CosechaFechaLog
from models.usuario import Usuario
from services.permissions_service import ensure_user_in_farm_or_admin, require_scopes

def _cycle_and_farm(db: Session, ciclo_id: int) -> tuple[Ciclo, int]:
    c = db.get(Ciclo, ciclo_id)
    if not c:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    return c, c.granja_id

# --- Plan ---

def upsert_plan(db: Session, user: Usuario, ciclo_id: int, nota_operativa: str | None) -> PlanCosechas:
    c, granja_id = _cycle_and_farm(db, ciclo_id)
    require_scopes(db, user, granja_id, {"harvest:plan"})
    plan = db.query(PlanCosechas).filter(PlanCosechas.ciclo_id == ciclo_id).first()
    if plan:
        plan.nota_operativa = nota_operativa
    else:
        plan = PlanCosechas(ciclo_id=ciclo_id, nota_operativa=nota_operativa, created_by=user.usuario_id)
        db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan

def get_plan(db: Session, user: Usuario, ciclo_id: int) -> PlanCosechas | None:
    c, granja_id = _cycle_and_farm(db, ciclo_id)
    ensure_user_in_farm_or_admin(db, user, granja_id)
    return db.query(PlanCosechas).filter(PlanCosechas.ciclo_id == ciclo_id).first()

# --- Olas ---

def upsert_wave(db: Session, user: Usuario, plan_id: int, body) -> CosechaOla:
    plan = db.get(PlanCosechas, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="harvest_plan_not_found")
    c, granja_id = _cycle_and_farm(db, plan.ciclo_id)
    require_scopes(db, user, granja_id, {"harvest:plan"})
    if body.ventana_inicio > body.ventana_fin:
        raise HTTPException(status_code=422, detail="invalid_window")

    ola = CosechaOla(
        plan_cosechas_id=plan_id,
        nombre=body.nombre,
        tipo=body.tipo,
        ventana_inicio=body.ventana_inicio,
        ventana_fin=body.ventana_fin,
        objetivo_retiro_org_m2=body.objetivo_retiro_org_m2,
        estado=body.estado or "p",
        orden=body.orden,
        notas=body.notas,
        created_by=user.usuario_id,
    )
    db.add(ola)
    db.commit()
    db.refresh(ola)
    return ola

def list_waves(db: Session, user: Usuario, plan_id: int) -> List[CosechaOla]:
    plan = db.get(PlanCosechas, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="harvest_plan_not_found")
    c, granja_id = _cycle_and_farm(db, plan.ciclo_id)
    ensure_user_in_farm_or_admin(db, user, granja_id)
    return (
        db.query(CosechaOla)
        .filter(CosechaOla.plan_cosechas_id == plan_id)
        .order_by(asc(CosechaOla.orden), asc(CosechaOla.ventana_inicio))
        .all()
    )

# --- Generación de cosechas por estanque ---

def _evenly_distribute_dates(start: date, end: date, n: int) -> List[date]:
    if n <= 1:
        return [start]
    total_days = (end - start).days
    if total_days < 0:
        total_days = 0
    step = max(0, total_days // (n - 1))
    return [start + timedelta(days=step * i) for i in range(n)]

def generate_pond_harvests(db: Session, user: Usuario, ola_id: int) -> int:
    ola = db.get(CosechaOla, ola_id)
    if not ola:
        raise HTTPException(status_code=404, detail="harvest_wave_not_found")
    plan = db.get(PlanCosechas, ola.plan_cosechas_id)
    c, granja_id = _cycle_and_farm(db, plan.ciclo_id)
    require_scopes(db, user, granja_id, {"harvest:plan"})
    # estanques de la granja
    ponds = db.query(Estanque).filter(Estanque.granja_id == granja_id).order_by(asc(Estanque.estanque_id)).all()
    if not ponds:
        return 0
    # evitar duplicados por ola+estanque
    existing = db.query(CosechaEstanque.estanque_id).filter(CosechaEstanque.cosecha_ola_id == ola_id).all()
    existing_ids = {e[0] for e in existing}
    ponds = [p for p in ponds if p.estanque_id not in existing_ids]
    if not ponds:
        return 0
    dates = _evenly_distribute_dates(ola.ventana_inicio, ola.ventana_fin, len(ponds))
    bulk = []
    for p, d in zip(ponds, dates):
        bulk.append(
            CosechaEstanque(
                estanque_id=p.estanque_id,
                cosecha_ola_id=ola_id,
                estado="p",
                fecha_cosecha=d,
                created_by=user.usuario_id,
            )
        )
    if bulk:
        db.bulk_save_objects(bulk)
        db.commit()
    return len(bulk)

def list_harvests_by_cycle(db: Session, user: Usuario, ciclo_id: int) -> List[CosechaEstanque]:
    c, granja_id = _cycle_and_farm(db, ciclo_id)
    ensure_user_in_farm_or_admin(db, user, granja_id)
    # Traer todas las cosechas del ciclo via join por olas -> plan
    from sqlalchemy import select, join
    j = join(CosechaEstanque, CosechaOla, CosechaEstanque.cosecha_ola_id == CosechaOla.cosecha_ola_id) \
        .join(PlanCosechas, CosechaOla.plan_cosechas_id == PlanCosechas.plan_cosechas_id)
    stmt = (
        select(CosechaEstanque)
        .select_from(j)
        .where(PlanCosechas.ciclo_id == ciclo_id)
        .order_by(
            CosechaEstanque.fecha_cosecha.is_(None).asc(),
            asc(CosechaEstanque.fecha_cosecha),
            asc(CosechaEstanque.cosecha_ola_id),
        )
    )
    return [row[0] for row in db.execute(stmt).all()]

# --- Reprogramación ---

def reprogram_harvest(db: Session, user: Usuario, cosecha_estanque_id: int, fecha_nueva: date, motivo: str | None) -> CosechaEstanque:
    ce = db.get(CosechaEstanque, cosecha_estanque_id)
    if not ce:
        raise HTTPException(status_code=404, detail="harvest_pond_not_found")
    ola = db.get(CosechaOla, ce.cosecha_ola_id)
    plan = db.get(PlanCosechas, ola.plan_cosechas_id)
    c, granja_id = _cycle_and_farm(db, plan.ciclo_id)
    require_scopes(db, user, granja_id, {"harvest:reprogram"})
    if ce.estado != "p":
        raise HTTPException(status_code=409, detail="cannot_reprogram_non_planned")

    log = CosechaFechaLog(
        cosecha_estanque_id=ce.cosecha_estanque_id,
        fecha_anterior=ce.fecha_cosecha,
        fecha_nueva=fecha_nueva,
        motivo=motivo,
        changed_by=user.usuario_id,
    )
    db.add(log)
    ce.fecha_cosecha = fecha_nueva
    ola.estado = "r"  # marcar ola como reprogramada
    db.commit()
    db.refresh(ce)
    return ce

# --- Confirmación ---

def _derive_from_biomass(biomasa_kg: float, pp_g: float, superficie_m2) -> float:
    # org/m2 = (biomasa_kg * 1000 g/kg) / (pp_g g/org * superficie_m2 m2)
    return float(biomasa_kg) * 1000.0 / (float(pp_g) * float(superficie_m2))

def _derive_from_density(densidad_org_m2: float, pp_g: float, superficie_m2) -> float:
    # kg = densidad_org_m2 * superficie_m2 * (pp_g / 1000)
    return float(densidad_org_m2) * float(superficie_m2) * (float(pp_g) / 1000.0)

def confirm_harvest(db: Session, user: Usuario, cosecha_estanque_id: int, body) -> CosechaEstanque:
    ce = db.get(CosechaEstanque, cosecha_estanque_id)
    if not ce:
        raise HTTPException(status_code=404, detail="harvest_pond_not_found")
    ola = db.get(CosechaOla, ce.cosecha_ola_id)
    plan = db.get(PlanCosechas, ola.plan_cosechas_id)
    c, granja_id = _cycle_and_farm(db, plan.ciclo_id)
    require_scopes(db, user, granja_id, {"harvest:confirm"})
    if ce.estado != "p":
        raise HTTPException(status_code=409, detail="already_confirmed_or_cancelled")

    pond = db.get(Estanque, ce.estanque_id)
    if not pond:
        raise HTTPException(status_code=404, detail="pond_not_found")

    if body.biomasa_kg is None and body.densidad_retirada_org_m2 is None:
        raise HTTPException(status_code=422, detail="one_of_biomasa_or_densidad_required")

    pp_g = body.pp_g
    biomasa_kg = body.biomasa_kg
    densidad_org_m2 = body.densidad_retirada_org_m2

    # Derivar la otra métrica según corresponda (sin SOB; confirmación es sobre retirado real)
    if biomasa_kg is None:
        biomasa_kg = _derive_from_density(densidad_org_m2, pp_g, pond.superficie_m2)
    elif densidad_org_m2 is None:
        densidad_org_m2 = _derive_from_biomass(biomasa_kg, pp_g, pond.superficie_m2)

    ce.fecha_cosecha = body.fecha_cosecha
    ce.pp_g = pp_g
    ce.biomasa_kg = biomasa_kg
    ce.densidad_retirada_org_m2 = densidad_org_m2
    ce.notas = body.notas
    ce.estado = "c"
    ce.confirmado_por = user.usuario_id
    ce.confirmado_event_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(ce)
    return ce

# --- Cancelación de ola ---

def cancel_wave(db: Session, user: Usuario, ola_id: int) -> dict:
    ola = db.get(CosechaOla, ola_id)
    if not ola:
        raise HTTPException(status_code=404, detail="harvest_wave_not_found")
    plan = db.get(PlanCosechas, ola.plan_cosechas_id)
    c, granja_id = _cycle_and_farm(db, plan.ciclo_id)
    require_scopes(db, user, granja_id, {"harvest:cancel"})

    ola.estado = "x"
    # cancelar solo planeadas (no tocar confirmadas)
    q = (
        db.query(CosechaEstanque)
        .filter(CosechaEstanque.cosecha_ola_id == ola_id, CosechaEstanque.estado == "p")
    )
    count = 0
    for ce in q.all():
        ce.estado = "x"
        count += 1
    db.commit()
    return {"cancelled": count}

def list_harvests_by_wave(db: Session, user: Usuario, plan_id: int, ola_id: int) -> List[CosechaEstanque]:
    ola = db.get(CosechaOla, ola_id)
    if not ola or ola.plan_cosechas_id != plan_id:
        raise HTTPException(status_code=404, detail="harvest_wave_not_found")
    plan = db.get(PlanCosechas, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="harvest_plan_not_found")
    ciclo = db.get(Ciclo, plan.ciclo_id)
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    # Portátil MySQL/Postgres: NULLs al final sin "NULLS LAST"
    q = (
        db.query(CosechaEstanque)
        .filter(CosechaEstanque.cosecha_ola_id == ola_id)
        .order_by(
            CosechaEstanque.fecha_cosecha.is_(None).asc(),
            asc(CosechaEstanque.fecha_cosecha),
            asc(CosechaEstanque.estanque_id),
        )
    )
    return q.all()

def list_waves_with_ponds(db: Session, user: Usuario, plan_id: int):
    plan = db.get(PlanCosechas, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="harvest_plan_not_found")
    ciclo = db.get(Ciclo, plan.ciclo_id)
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    olas = (
        db.query(CosechaOla)
        .filter(CosechaOla.plan_cosechas_id == plan_id)
        .order_by(asc(CosechaOla.orden), asc(CosechaOla.ventana_inicio))
        .all()
    )

    result = []
    for o in olas:
        ponds = (
            db.query(CosechaEstanque)
            .filter(CosechaEstanque.cosecha_ola_id == o.cosecha_ola_id)
            .order_by(
                CosechaEstanque.fecha_cosecha.is_(None).asc(),
                asc(CosechaEstanque.fecha_cosecha),
                asc(CosechaEstanque.estanque_id),
            )
            .all()
        )
        result.append((o, ponds))
    return result