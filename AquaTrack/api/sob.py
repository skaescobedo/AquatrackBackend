# api/sob.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from utils.db import get_db
from utils.dependencies import get_current_active_user
from models.ciclo import Ciclo
from models.estanque import Estanque
from models.sob_cambio_log import SOBCambioLog
from schemas.sob import SOBCambioCreate, SOBCambioOut

router = APIRouter(prefix="/ciclos/{ciclo_id}/estanques/{estanque_id}/sob-cambios")

def ensure_refs(db: Session, ciclo_id: int, estanque_id: int):
    if not db.query(Ciclo).get(ciclo_id):
        raise HTTPException(404, "Ciclo no encontrado")
    if not db.query(Estanque).get(estanque_id):
        raise HTTPException(404, "Estanque no encontrado")

def get_log_or_404(db: Session, ciclo_id: int, estanque_id: int, log_id: int) -> SOBCambioLog:
    obj = db.query(SOBCambioLog).filter(
        SOBCambioLog.sob_cambio_log_id == log_id,
        SOBCambioLog.ciclo_id == ciclo_id,
        SOBCambioLog.estanque_id == estanque_id
    ).first()
    if not obj: raise HTTPException(404, "Log de SOB no encontrado")
    return obj

@router.get("/", response_model=List[SOBCambioOut])
def list_logs(ciclo_id: int, estanque_id: int, db: Session = Depends(get_db), _=Depends(get_current_active_user)):
    ensure_refs(db, ciclo_id, estanque_id)
    return db.query(SOBCambioLog).filter(
        SOBCambioLog.ciclo_id == ciclo_id,
        SOBCambioLog.estanque_id == estanque_id
    ).order_by(SOBCambioLog.changed_at.desc()).all()

@router.post("/", response_model=SOBCambioOut, status_code=201)
def create_log(ciclo_id: int, estanque_id: int, data: SOBCambioCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    ensure_refs(db, ciclo_id, estanque_id)
    obj = SOBCambioLog(ciclo_id=ciclo_id, estanque_id=estanque_id, changed_by=user.usuario_id, **data.model_dump(exclude_unset=True))
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.get("/{log_id}", response_model=SOBCambioOut)
def retrieve_log(ciclo_id: int, estanque_id: int, log_id: int, db: Session = Depends(get_db), _=Depends(get_current_active_user)):
    return get_log_or_404(db, ciclo_id, estanque_id, log_id)
