from datetime import timedelta, date
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, asc
from models.ciclo import Ciclo
from models.granja import Granja
from models.estanque import Estanque
from models.siembra_plan import SiembraPlan
from models.siembra_estanque import SiembraEstanque
from models.siembra_fecha_log import SiembraFechaLog
from models.usuario import Usuario
from services.permissions_service import ensure_user_in_farm_or_admin, require_scopes

def _cycle_and_farm(db: Session, ciclo_id: int) -> tuple[Ciclo, int]:
    c = db.get(Ciclo, ciclo_id)
    if not c:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    return c, c.granja_id

def get_plan(db: Session, user: Usuario, ciclo_id: int) -> SiembraPlan | None:
    c, granja_id = _cycle_and_farm(db, ciclo_id)
    ensure_user_in_farm_or_admin(db, user, granja_id)
    return db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()

def upsert_plan(db: Session, user: Usuario, ciclo_id: int, body) -> SiembraPlan:
    c, granja_id = _cycle_and_farm(db, ciclo_id)
    require_scopes(db, user, granja_id, {"seeding:plan"})
    if body.ventana_inicio > body.ventana_fin:
        raise HTTPException(status_code=422, detail="invalid_window")

    sp = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if sp:
        sp.ventana_inicio = body.ventana_inicio
        sp.ventana_fin = body.ventana_fin
        sp.densidad_org_m2 = body.densidad_org_m2
        sp.talla_inicial_g = body.talla_inicial_g
        sp.observaciones = body.observaciones
    else:
        sp = SiembraPlan(
            ciclo_id=ciclo_id,
            ventana_inicio=body.ventana_inicio,
            ventana_fin=body.ventana_fin,
            densidad_org_m2=body.densidad_org_m2,
            talla_inicial_g=body.talla_inicial_g,
            observaciones=body.observaciones,
            created_by=user.usuario_id,
        )
        db.add(sp)
    db.commit()
    db.refresh(sp)
    return sp

def _evenly_distribute_dates(start: date, end: date, n: int) -> List[date]:
    if n <= 1:
        return [start]
    total_days = (end - start).days
    if total_days < 0:
        total_days = 0
    step = max(0, total_days // (n - 1))
    return [start + timedelta(days=step * i) for i in range(n)]

def generate_pond_plans(db: Session, user: Usuario, plan_id: int) -> int:
    sp = db.get(SiembraPlan, plan_id)
    if not sp:
        raise HTTPException(status_code=404, detail="seeding_plan_not_found")
    c, granja_id = _cycle_and_farm(db, sp.ciclo_id)
    require_scopes(db, user, granja_id, {"seeding:plan"})

    # estanques de la granja
    ponds = db.query(Estanque).filter(Estanque.granja_id == granja_id).order_by(Estanque.estanque_id.asc()).all()
    if not ponds:
        return 0

    # evita duplicados: filtra los que ya tengan siembra para este plan
    existing = db.query(SiembraEstanque.estanque_id).filter(SiembraEstanque.siembra_plan_id == plan_id).all()
    existing_ids = {e[0] for e in existing}
    ponds = [p for p in ponds if p.estanque_id not in existing_ids]
    if not ponds:
        return 0

    dates = _evenly_distribute_dates(sp.ventana_inicio, sp.ventana_fin, len(ponds))
    bulk = []
    for p, d in zip(ponds, dates):
        bulk.append(
            SiembraEstanque(
                siembra_plan_id=plan_id,
                estanque_id=p.estanque_id,
                estado="p",
                fecha_tentativa=d,
                created_by=user.usuario_id,
            )
        )
    if bulk:
        db.bulk_save_objects(bulk)
        db.commit()
    return len(bulk)

def list_pond_seedings(db: Session, user: Usuario, ciclo_id: int) -> List[SiembraEstanque]:
    sp = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not sp:
        return []
    c, granja_id = _cycle_and_farm(db, ciclo_id)
    ensure_user_in_farm_or_admin(db, user, granja_id)
    return (
        db.query(SiembraEstanque)
        .filter(SiembraEstanque.siembra_plan_id == sp.siembra_plan_id)
        .order_by(
            SiembraEstanque.fecha_tentativa.is_(None).asc(),  # primero NO nulos; los NULL se van al final
            asc(SiembraEstanque.fecha_tentativa),
        )
        .all()
    )

def reprogram_pond(db: Session, user: Usuario, siembra_estanque_id: int, fecha_nueva, motivo: str | None) -> SiembraEstanque:
    se = db.get(SiembraEstanque, siembra_estanque_id)
    if not se:
        raise HTTPException(status_code=404, detail="seeding_pond_not_found")
    sp = db.get(SiembraPlan, se.siembra_plan_id)
    c, granja_id = _cycle_and_farm(db, sp.ciclo_id)
    require_scopes(db, user, granja_id, {"seeding:reprogram"})
    if se.estado != "p":
        raise HTTPException(status_code=409, detail="cannot_reprogram_non_planned")
    # ventana válida (opcionalmente puedes restringir dentro de ventana del plan)
    log = SiembraFechaLog(
        siembra_estanque_id=se.siembra_estanque_id,
        fecha_anterior=se.fecha_tentativa,
        fecha_nueva=fecha_nueva,
        motivo=motivo,
        changed_by=user.usuario_id,
    )
    db.add(log)
    se.fecha_tentativa = fecha_nueva
    db.commit()
    db.refresh(se)
    return se

def confirm_pond(db: Session, user: Usuario, siembra_estanque_id: int, body) -> SiembraEstanque:
    se = db.get(SiembraEstanque, siembra_estanque_id)
    if not se:
        raise HTTPException(status_code=404, detail="seeding_pond_not_found")
    sp = db.get(SiembraPlan, se.siembra_plan_id)
    c, granja_id = _cycle_and_farm(db, sp.ciclo_id)
    require_scopes(db, user, granja_id, {"seeding:confirm"})
    if se.estado != "p":
        raise HTTPException(status_code=409, detail="already_confirmed")

    se.fecha_siembra = body.fecha_siembra
    se.estado = "f"

    # Solo si vienen en el payload (no pises valores previos si el cliente omite campos)
    if "lote" in body.__fields_set__:
        se.lote = body.lote
    if "densidad_override_org_m2" in body.__fields_set__:
        se.densidad_override_org_m2 = body.densidad_override_org_m2  # None = limpiar, >0 = setear
    if "talla_inicial_override_g" in body.__fields_set__:
        se.talla_inicial_override_g = body.talla_inicial_override_g
    if "observaciones" in body.__fields_set__:
        se.observaciones = body.observaciones

    db.commit()
    db.refresh(se)
    return se

def update_overrides(db: Session, user: Usuario, siembra_estanque_id: int, body) -> SiembraEstanque:
    se = db.get(SiembraEstanque, siembra_estanque_id)
    if not se:
        raise HTTPException(status_code=404, detail="seeding_pond_not_found")
    sp = db.get(SiembraPlan, se.siembra_plan_id)
    _, granja_id = _cycle_and_farm(db, sp.ciclo_id)
    require_scopes(db, user, granja_id, {"seeding:plan"})  # o reprogram según tu política

    if "densidad_override_org_m2" in body.__fields_set__:
        se.densidad_override_org_m2 = body.densidad_override_org_m2
    if "talla_inicial_override_g" in body.__fields_set__:
        se.talla_inicial_override_g = body.talla_inicial_override_g
    if "lote" in body.__fields_set__:
        se.lote = body.lote
    if "observaciones" in body.__fields_set__:
        se.observaciones = body.observaciones

    db.commit()
    db.refresh(se)
    return se
