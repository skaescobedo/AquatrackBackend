from fastapi import APIRouter, Depends, Path, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from utils.db import get_db
from utils.dependencies import get_current_user
from models.usuario import Usuario
from schemas.harvest import (
    CosechaOlaUpsert, CosechaOlaOut, CosechaEstanqueOut, CosechaOlaWithPondsOut
)
from services.harvest_service import (
    upsert_wave, list_waves, generate_pond_harvests, cancel_wave,
    list_harvests_by_wave, list_waves_with_ponds
)

router = APIRouter(prefix="/harvest/plan/{plan_id}/waves", tags=["harvest"])

@router.post("", response_model=CosechaOlaOut)
def upsert_wave_endpoint(
    plan_id: int = Path(..., gt=0),
    body: CosechaOlaUpsert = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ola = upsert_wave(db, user, plan_id, body)
    return {
        "cosecha_ola_id": ola.cosecha_ola_id,
        "plan_cosechas_id": ola.plan_cosechas_id,
        "nombre": ola.nombre,
        "tipo": ola.tipo,
        "ventana_inicio": ola.ventana_inicio,
        "ventana_fin": ola.ventana_fin,
        "objetivo_retiro_org_m2": float(ola.objetivo_retiro_org_m2) if ola.objetivo_retiro_org_m2 is not None else None,
        "estado": ola.estado,
        "orden": ola.orden,
        "notas": ola.notas,
    }

@router.get("", response_model=List[CosechaOlaOut])
def list_waves_endpoint(
    plan_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    items = list_waves(db, user, plan_id)
    return [
        {
            "cosecha_ola_id": o.cosecha_ola_id,
            "plan_cosechas_id": o.plan_cosechas_id,
            "nombre": o.nombre,
            "tipo": o.tipo,
            "ventana_inicio": o.ventana_inicio,
            "ventana_fin": o.ventana_fin,
            "objetivo_retiro_org_m2": float(o.objetivo_retiro_org_m2) if o.objetivo_retiro_org_m2 is not None else None,
            "estado": o.estado,
            "orden": o.orden,
            "notas": o.notas,
        } for o in items
    ]

# >>> NUEVO: listar cosechas por estanque **de una ola**
@router.get("/{ola_id}/ponds", response_model=List[CosechaEstanqueOut])
def list_ponds_by_wave_endpoint(
    plan_id: int = Path(..., gt=0),
    ola_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    items = list_harvests_by_wave(db, user, plan_id, ola_id)
    return [
        {
            "cosecha_estanque_id": ce.cosecha_estanque_id,
            "cosecha_ola_id": ce.cosecha_ola_id,
            "estanque_id": ce.estanque_id,
            "estado": ce.estado,
            "fecha_cosecha": ce.fecha_cosecha,
            "pp_g": float(ce.pp_g) if ce.pp_g is not None else None,
            "biomasa_kg": float(ce.biomasa_kg) if ce.biomasa_kg is not None else None,
            "densidad_retirada_org_m2": float(ce.densidad_retirada_org_m2) if ce.densidad_retirada_org_m2 is not None else None,
            "notas": ce.notas,
        } for ce in items
    ]

# >>> NUEVO: listar **todas** las olas de un plan con sus estanques anidados
@router.get("/with-ponds", response_model=List[CosechaOlaWithPondsOut])
def list_waves_with_ponds_endpoint(
    plan_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    pairs = list_waves_with_ponds(db, user, plan_id)
    resp = []
    for o, ponds in pairs:
        resp.append({
            "ola": {
                "cosecha_ola_id": o.cosecha_ola_id,
                "plan_cosechas_id": o.plan_cosechas_id,
                "nombre": o.nombre,
                "tipo": o.tipo,
                "ventana_inicio": o.ventana_inicio,
                "ventana_fin": o.ventana_fin,
                "objetivo_retiro_org_m2": float(o.objetivo_retiro_org_m2) if o.objetivo_retiro_org_m2 is not None else None,
                "estado": o.estado,
                "orden": o.orden,
                "notas": o.notas,
            },
            "ponds": [
                {
                    "cosecha_estanque_id": ce.cosecha_estanque_id,
                    "cosecha_ola_id": ce.cosecha_ola_id,
                    "estanque_id": ce.estanque_id,
                    "estado": ce.estado,
                    "fecha_cosecha": ce.fecha_cosecha,
                    "pp_g": float(ce.pp_g) if ce.pp_g is not None else None,
                    "biomasa_kg": float(ce.biomasa_kg) if ce.biomasa_kg is not None else None,
                    "densidad_retirada_org_m2": float(ce.densidad_retirada_org_m2) if ce.densidad_retirada_org_m2 is not None else None,
                    "notas": ce.notas,
                } for ce in ponds
            ]
        })
    return resp

@router.post("/{ola_id}/generate")
def generate_endpoint(
    plan_id: int = Path(..., gt=0),
    ola_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    created = generate_pond_harvests(db, user, ola_id)
    return {"created": created}

@router.post("/{ola_id}/cancel")
def cancel_wave_endpoint(
    plan_id: int = Path(..., gt=0),
    ola_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    result = cancel_wave(db, user, ola_id)
    return result
