# api/parametros.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from utils.db import get_db
from utils.dependencies import get_current_active_user
from models.ciclo import Ciclo
from models.parametro_ciclo import ParametroCicloVersion
from schemas.parametros import ParametroCicloVersionCreate, ParametroCicloVersionUpdate, ParametroCicloVersionOut

router = APIRouter(prefix="/ciclos/{ciclo_id}/parametros/versiones")

def get_ciclo_or_404(db: Session, ciclo_id: int) -> Ciclo:
    obj = db.query(Ciclo).get(ciclo_id)
    if not obj: raise HTTPException(404, "Ciclo no encontrado")
    return obj

def get_pcv_or_404(db: Session, ciclo_id: int, pcv_id: int) -> ParametroCicloVersion:
    obj = db.query(ParametroCicloVersion).filter(
        ParametroCicloVersion.parametro_ciclo_version_id == pcv_id,
        ParametroCicloVersion.ciclo_id == ciclo_id
    ).first()
    if not obj: raise HTTPException(404, "Versión de parámetros no encontrada")
    return obj

@router.get("/", response_model=List[ParametroCicloVersionOut])
def list_pcv(ciclo_id: int, db: Session = Depends(get_db), _=Depends(get_current_active_user)):
    get_ciclo_or_404(db, ciclo_id)
    return db.query(ParametroCicloVersion).filter(ParametroCicloVersion.ciclo_id == ciclo_id).all()

@router.post("/", response_model=ParametroCicloVersionOut, status_code=201)
def create_pcv(ciclo_id: int, data: ParametroCicloVersionCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    get_ciclo_or_404(db, ciclo_id)
    obj = ParametroCicloVersion(ciclo_id=ciclo_id, updated_by=user.usuario_id, **data.model_dump(exclude_unset=True))
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.get("/{pcv_id}", response_model=ParametroCicloVersionOut)
def retrieve_pcv(ciclo_id: int, pcv_id: int, db: Session = Depends(get_db), _=Depends(get_current_active_user)):
    return get_pcv_or_404(db, ciclo_id, pcv_id)

@router.put("/{pcv_id}", response_model=ParametroCicloVersionOut)
def update_pcv(ciclo_id: int, pcv_id: int, data: ParametroCicloVersionUpdate, db: Session = Depends(get_db), _=Depends(get_current_active_user)):
    obj = get_pcv_or_404(db, ciclo_id, pcv_id)
    for k, v in data.model_dump(exclude_unset=True).items(): setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj

@router.delete("/{pcv_id}", status_code=204)
def delete_pcv(ciclo_id: int, pcv_id: int, db: Session = Depends(get_db), _=Depends(get_current_active_user)):
    obj = get_pcv_or_404(db, ciclo_id, pcv_id)
    db.delete(obj); db.commit()
    return
