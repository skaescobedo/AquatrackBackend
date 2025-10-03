from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from utils.db import get_db
from models.granja import Granja
from schemas.granja import GranjaOut, GranjaCreate, GranjaUpdate
from utils.dependencies import get_current_active_user

router = APIRouter(prefix="/granjas", tags=["granjas"])

@router.post("/", response_model=GranjaOut)
def crear_granja(data: GranjaCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    granja = Granja(**data.dict())
    db.add(granja)
    db.commit()
    db.refresh(granja)
    return granja

@router.get("/", response_model=list[GranjaOut])
def listar_granjas(db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    return db.query(Granja).all()

@router.get("/{granja_id}", response_model=GranjaOut)
def obtener_granja(granja_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    granja = db.query(Granja).filter_by(granja_id=granja_id).first()
    if not granja:
        raise HTTPException(status_code=404, detail="Granja no encontrada")
    return granja

@router.put("/{granja_id}", response_model=GranjaOut)
def actualizar_granja(granja_id: int, data: GranjaUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    granja = db.query(Granja).filter_by(granja_id=granja_id).first()
    if not granja:
        raise HTTPException(status_code=404, detail="Granja no encontrada")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(granja, k, v)
    db.commit()
    db.refresh(granja)
    return granja

@router.delete("/{granja_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_granja(granja_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    granja = db.query(Granja).filter_by(granja_id=granja_id).first()
    if not granja:
        raise HTTPException(status_code=404, detail="Granja no encontrada")
    db.delete(granja)
    db.commit()
    return None
