from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_active_user
from models.ciclo import Ciclo
from models.ciclo_resumen import CicloResumen
from schemas.ciclo import CicloOut, CicloCreate, CicloUpdate
from schemas.ciclo_resumen import CicloResumenOut, CicloResumenCreate, CicloResumenUpdate

router = APIRouter(prefix="/ciclos", tags=["ciclos"])

# --- Ciclo ---
@router.post("/", response_model=CicloOut)
def crear_ciclo(data: CicloCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    ciclo = Ciclo(**data.dict())
    db.add(ciclo)
    db.commit()
    db.refresh(ciclo)
    return ciclo

@router.get("/", response_model=list[CicloOut])
def listar_ciclos(db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    return db.query(Ciclo).all()

@router.get("/{ciclo_id}", response_model=CicloOut)
def obtener_ciclo(ciclo_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(Ciclo).filter_by(ciclo_id=ciclo_id).first()
    if not obj:
        raise HTTPException(404, "Ciclo no encontrado")
    return obj

@router.put("/{ciclo_id}", response_model=CicloOut)
def actualizar_ciclo(ciclo_id: int, data: CicloUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(Ciclo).filter_by(ciclo_id=ciclo_id).first()
    if not obj:
        raise HTTPException(404, "Ciclo no encontrado")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/{ciclo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_ciclo(ciclo_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(Ciclo).filter_by(ciclo_id=ciclo_id).first()
    if not obj:
        raise HTTPException(404, "Ciclo no encontrado")
    db.delete(obj)
    db.commit()
    return None

# --- CicloResumen ---
@router.post("/{ciclo_id}/resumen", response_model=CicloResumenOut)
def crear_resumen(ciclo_id: int, data: CicloResumenCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    if ciclo_id != data.ciclo_id:
        raise HTTPException(400, "ciclo_id inconsistente")
    if db.query(CicloResumen).filter_by(ciclo_id=ciclo_id).first():
        raise HTTPException(400, "Resumen ya existe para este ciclo")
    obj = CicloResumen(**data.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/{ciclo_id}/resumen", response_model=CicloResumenOut)
def obtener_resumen(ciclo_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(CicloResumen).filter_by(ciclo_id=ciclo_id).first()
    if not obj:
        raise HTTPException(404, "Resumen no encontrado")
    return obj

@router.put("/{ciclo_id}/resumen", response_model=CicloResumenOut)
def actualizar_resumen(ciclo_id: int, data: CicloResumenUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(CicloResumen).filter_by(ciclo_id=ciclo_id).first()
    if not obj:
        raise HTTPException(404, "Resumen no encontrado")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/{ciclo_id}/resumen", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_resumen(ciclo_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(CicloResumen).filter_by(ciclo_id=ciclo_id).first()
    if not obj:
        raise HTTPException(404, "Resumen no encontrado")
    db.delete(obj)
    db.commit()
    return None
