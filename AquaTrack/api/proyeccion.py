# routers/projections.py
from __future__ import annotations
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session
from sqlalchemy import func
from utils.db import get_db
from utils.dependencies import get_current_user
from models.usuario import Usuario
from models.proyeccion_linea import ProyeccionLinea

from schemas.proyeccion import (
    ProyeccionOut, ProyeccionLineaOut,
    ProyeccionReforecastIn, ProyeccionFromFileIn, FromFileResult, ImpactStats,
    ProyeccionFromPlansIn, FromPlansResult,
    PublishResult, ReforecastUpdateIn, ReforecastUpdateOut,   # <-- NUEVO
)
from services.projection_service import list_projections, get_projection_lines, reforecast, publish
from services.projection_ingest_service import ingest_from_file
from services.projection_from_plans_service import generate_from_plans
from services.reforecast_live_service import observe_and_rebuild  # <-- NUEVO

router = APIRouter(prefix="/projections", tags=["projections"])

@router.get("/cycles/{ciclo_id}", response_model=List[ProyeccionOut])
def list_by_cycle(
    ciclo_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    items = list_projections(db, user, ciclo_id)
    return [
        {
            "proyeccion_id": p.proyeccion_id,
            "ciclo_id": p.ciclo_id,
            "version": p.version,
            "descripcion": p.descripcion,
            "status": p.status,
            "is_current": bool(p.is_current),
            "published_at": p.published_at,
            "source_type": p.source_type,
            "parent_version_id": p.parent_version_id,
        } for p in items
    ]


@router.post("/cycles/{ciclo_id}/from-file", response_model=FromFileResult)
def from_file_endpoint(
    ciclo_id: int = Path(..., gt=0),
    body: ProyeccionFromFileIn = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    proy, warnings = ingest_from_file(
        db, user, ciclo_id=ciclo_id, archivo_id=body.archivo_id, force_reingest=body.force_reingest
    )

    lineas = (
        db.query(func.count(ProyeccionLinea.proyeccion_linea_id))
        .filter(ProyeccionLinea.proyeccion_id == proy.proyeccion_id)
        .scalar()
    ) or 0

    return {
        "proyeccion_id": proy.proyeccion_id,
        "ciclo_id": proy.ciclo_id,
        "lineas_insertadas": lineas,
        "status": proy.status,
        "is_current": bool(proy.is_current),
        "source_type": proy.source_type or "archivo",
        "warnings": warnings,
    }


@router.post("/cycles/{ciclo_id}/from-plans", response_model=FromPlansResult)
def from_plans_endpoint(
    ciclo_id: int = Path(..., gt=0),
    body: ProyeccionFromPlansIn = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    proy, warnings = generate_from_plans(db, user, ciclo_id=ciclo_id, payload=body)

    lineas = (
        db.query(func.count(ProyeccionLinea.proyeccion_linea_id))
        .filter(ProyeccionLinea.proyeccion_id == proy.proyeccion_id)
        .scalar()
    ) or 0

    return {
        "proyeccion_id": proy.proyeccion_id,
        "ciclo_id": proy.ciclo_id,
        "lineas_insertadas": lineas,
        "status": proy.status,
        "is_current": bool(proy.is_current),
        "source_type": proy.source_type or "planes",
        "warnings": warnings,
    }


@router.get("/{proyeccion_id}/lines", response_model=List[ProyeccionLineaOut])
def get_lines(
    proyeccion_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    lines = get_projection_lines(db, user, proyeccion_id)
    return [
        {
            "proyeccion_linea_id": l.proyeccion_linea_id,
            "semana_idx": l.semana_idx,
            "fecha_plan": l.fecha_plan,
            "pp_g": float(l.pp_g),
            "incremento_g_sem": float(l.incremento_g_sem) if l.incremento_g_sem is not None else None,
            "sob_pct_linea": float(l.sob_pct_linea),
            "cosecha_flag": bool(l.cosecha_flag),
            "retiro_org_m2": float(l.retiro_org_m2) if l.retiro_org_m2 is not None else None,
            "edad_dias": l.edad_dias,
            "nota": l.nota,
        } for l in lines
    ]


@router.post("/{proyeccion_id}/reforecast", response_model=ProyeccionOut)
def do_reforecast(
    proyeccion_id: int = Path(..., gt=0),
    body: ProyeccionReforecastIn = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    p = reforecast(db, user, proyeccion_id, (body.descripcion if body else None))
    return {
        "proyeccion_id": p.proyeccion_id,
        "ciclo_id": p.ciclo_id,
        "version": p.version,
        "descripcion": p.descripcion,
        "status": p.status,
        "is_current": bool(p.is_current),
        "published_at": p.published_at,
        "source_type": p.source_type,
        "parent_version_id": p.parent_version_id,
    }


@router.post("/{proyeccion_id}/publish", response_model=PublishResult)
def do_publish(
    proyeccion_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    result = publish(db, user, proyeccion_id)
    return {
        "applied": result["applied"],
        "impact_summary": result["impact_summary"],
        "seeding_locked": result.get("seeding_locked", False),
        "seeding_stats": ImpactStats(**result.get("seeding_stats", {"updated": 0, "deleted": 0, "created": 0})),
        "harvest_stats": ImpactStats(**result.get("harvest_stats", {"updated": 0, "deleted": 0, "created": 0})),
    }


# --- NUEVO: Anclar observaciones manuales en el reforecast vivo ---
@router.post("/cycles/{ciclo_id}/reforecast/update", response_model=ReforecastUpdateOut)
def reforecast_update_endpoint(
    ciclo_id: int = Path(..., gt=0),
    body: ReforecastUpdateIn = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    if (body.pp_g is None) and (body.sob_pct is None):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="at_least_one_of_pp_or_sob_required")
    event_date = body.event_date or datetime.utcnow().date()
    res = observe_and_rebuild(
        db, user, ciclo_id,
        event_date=event_date,
        set_pp=body.pp_g,
        set_sob=body.sob_pct,
        reason=body.reason or "manual",
        soft_if_other_draft=False,  # aquí sí queremos avisar si hay conflicto
    )
    if res.get("skipped"):
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=res.get("reason", "skipped"))
    return ReforecastUpdateOut(
        ciclo_id=ciclo_id,
        proyeccion_id=res["proyeccion_id"],
        week_idx=res["week_idx"],
        event_date=event_date,
        applied=True,
        anchors_applied={"pp": body.pp_g is not None, "sob": body.sob_pct is not None, "reason": body.reason or "manual"},
        lines_rebuilt=res["lines_rebuilt"],
    )
