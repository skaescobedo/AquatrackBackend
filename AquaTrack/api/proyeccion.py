# /api/proyeccion.py
from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_user
from models.usuario import Usuario
from sqlalchemy import func
from models.proyeccion_linea import ProyeccionLinea

from schemas.proyeccion import (
    ProyeccionOut, ProyeccionLineaOut, ProyeccionPublishIn, PublishResult,
    ProyeccionReforecastIn, ProyeccionFromFileIn, FromFileResult, ImpactStats
)
from services.projection_service import list_projections, get_projection_lines, reforecast, publish
from services.projection_ingest_service import ingest_from_file

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
    body: ProyeccionPublishIn = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    result = publish(db, user, proyeccion_id, body.sync_policy)
    # Adaptamos al schema incluyendo stats
    return {
        "applied": result["applied"],
        "sync_policy": body.sync_policy,
        "impact_summary": result["impact_summary"],
        "seeding_locked": result.get("seeding_locked", False),
        "seeding_stats": ImpactStats(**result.get("seeding_stats", {"updated": 0, "deleted": 0, "created": 0})),
        "harvest_stats": ImpactStats(**result.get("harvest_stats", {"updated": 0, "deleted": 0, "created": 0})),
    }
