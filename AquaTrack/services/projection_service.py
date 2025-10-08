from datetime import datetime, timezone
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from models.ciclo import Ciclo
from models.usuario import Usuario
from services.permissions_service import ensure_user_in_farm_or_admin

def list_projections(db: Session, user: Usuario, ciclo_id: int) -> List[Proyeccion]:
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)
    return (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id)
        .order_by(Proyeccion.created_at.desc())
        .all()
    )

def get_projection_lines(db: Session, user: Usuario, proyeccion_id: int) -> List[ProyeccionLinea]:
    p = db.get(Proyeccion, proyeccion_id)
    if not p:
        raise HTTPException(status_code=404, detail="projection_not_found")
    ciclo = db.get(Ciclo, p.ciclo_id)
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)
    return (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == proyeccion_id)
        .order_by(ProyeccionLinea.semana_idx.asc(), ProyeccionLinea.fecha_plan.asc())
        .all()
    )

def reforecast(db: Session, user: Usuario, proyeccion_id: int, descripcion: str | None) -> Proyeccion:
    src = db.get(Proyeccion, proyeccion_id)
    if not src:
        raise HTTPException(status_code=404, detail="projection_not_found")
    ciclo = db.get(Ciclo, src.ciclo_id)
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    # no permitir dos borradores simultáneos por ciclo
    existing_draft = (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == src.ciclo_id, Proyeccion.status == "b")
        .first()
    )
    if existing_draft:
        raise HTTPException(status_code=409, detail="draft_projection_already_exists")

    # nueva versión borrador encadenada a parent_version_id
    count_versions = db.query(func.count(Proyeccion.proyeccion_id)).filter(Proyeccion.ciclo_id == src.ciclo_id).scalar() or 0
    new_version = f"v{count_versions + 1}"

    draft = Proyeccion(
        ciclo_id=src.ciclo_id,
        version=new_version,
        descripcion=descripcion or "Borrador reforecast de " + src.version,
        status="b",
        is_current=False,
        creada_por=user.usuario_id,
        source_type="reforecast",
        parent_version_id=src.proyeccion_id,
    )
    db.add(draft)
    db.flush()  # obtiene id

    # clonar líneas (como base de trabajo)
    lines = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == src.proyeccion_id)
        .all()
    )
    clones = []
    for l in lines:
        clones.append(
            ProyeccionLinea(
                proyeccion_id=draft.proyeccion_id,
                edad_dias=l.edad_dias,
                semana_idx=l.semana_idx,
                fecha_plan=l.fecha_plan,
                pp_g=l.pp_g,
                incremento_g_sem=l.incremento_g_sem,
                sob_pct_linea=l.sob_pct_linea,
                cosecha_flag=l.cosecha_flag,
                retiro_org_m2=l.retiro_org_m2,
                nota=l.nota,
            )
        )
    if clones:
        db.bulk_save_objects(clones)

    db.commit()
    db.refresh(draft)
    return draft

def publish(db: Session, user: Usuario, proyeccion_id: int, sync_policy: str):
    if sync_policy not in ("none", "sync", "regen"):
        raise HTTPException(status_code=422, detail="invalid_sync_policy")

    p = db.get(Proyeccion, proyeccion_id)
    if not p:
        raise HTTPException(status_code=404, detail="projection_not_found")
    ciclo = db.get(Ciclo, p.ciclo_id)
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    # marcar como vigente y cerrar otras 'current'
    current = (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == p.ciclo_id, Proyeccion.is_current == True)
        .all()
    )
    for c in current:
        if c.proyeccion_id != p.proyeccion_id:
            c.is_current = False

    p.is_current = True
    p.status = "p"
    p.published_at = datetime.now(timezone.utc)

    # En Sprint 3 NO tocamos planeado: solo devolvemos un resumen
    impact = "Planes de siembra/cosecha no disponibles en Sprint 3; no se aplican cambios al planeado."
    db.commit()
    db.refresh(p)
    return {
        "applied": False,
        "sync_policy": sync_policy,
        "impact_summary": impact,
        "proyeccion_id": p.proyeccion_id,
    }
