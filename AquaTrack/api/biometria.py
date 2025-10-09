from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from utils.db import get_db
from utils.dependencies import get_current_user
from models.usuario import Usuario
from schemas.biometria import BiometriaCreate, BiometriaOut
from services.biometria_service import create_biometry, list_biometry

router = APIRouter(prefix="/cycles/{ciclo_id}/biometry", tags=["biometry"])

@router.post("", response_model=BiometriaOut)
def create_bio_endpoint(
    ciclo_id: int = Path(..., gt=0),
    body: BiometriaCreate = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    bio = create_biometry(db, user, ciclo_id, body)
    return {
        "biometria_id": bio.biometria_id,
        "ciclo_id": bio.ciclo_id,
        "estanque_id": bio.estanque_id,
        "fecha": bio.fecha,
        "created_at": bio.created_at,
        "n_muestra": bio.n_muestra,
        "peso_muestra_g": float(bio.peso_muestra_g),
        "pp_g": float(bio.pp_g),
        "incremento_g_sem": float(bio.incremento_g_sem) if bio.incremento_g_sem is not None else None,
        "sob_usada_pct": float(bio.sob_usada_pct),
        "sob_fuente": bio.sob_fuente,
        "actualiza_sob_operativa": int(bio.actualiza_sob_operativa),
        "notas": bio.notas,
    }

@router.get("", response_model=List[BiometriaOut])
def list_bio_endpoint(
    ciclo_id: int = Path(..., gt=0),
    estanque_id: Optional[int] = Query(default=None),
    created_from: Optional[datetime] = Query(default=None),
    created_to: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    items = list_biometry(db, user, ciclo_id, estanque_id, created_from, created_to)
    return [
        {
            "biometria_id": b.biometria_id,
            "ciclo_id": b.ciclo_id,
            "estanque_id": b.estanque_id,
            "fecha": b.fecha,
            "created_at": b.created_at,
            "n_muestra": b.n_muestra,
            "peso_muestra_g": float(b.peso_muestra_g),
            "pp_g": float(b.pp_g),
            "incremento_g_sem": float(b.incremento_g_sem) if b.incremento_g_sem is not None else None,
            "sob_usada_pct": float(b.sob_usada_pct),
            "sob_fuente": b.sob_fuente,
            "actualiza_sob_operativa": int(b.actualiza_sob_operativa),
            "notas": b.notas,
        } for b in items
    ]
