from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from utils.db import get_db
from models.estanque import Estanque
from schemas.estanque import EstanqueOut, EstanqueCreate, EstanqueUpdate
from utils.dependencies import get_current_active_user

router = APIRouter(prefix="/estanques", tags=["estanques"])

@router.post("/", response_model=EstanqueOut)
def crear_estanque(data: EstanqueCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    estanque = Estanque(**data.dict())
    db.add(estanque)
    db.commit()
    db.refresh(estanque)
    return estanque

@router.get("/", response_model=list[EstanqueOut])
def listar_estanques(db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    return db.query(Estanque).all()

@router.get("/{estanque_id}", response_model=EstanqueOut)
def obtener_estanque(estanque_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    estanque = db.query(Estanque).filter_by(estanque_id=estanque_id).first()
    if not estanque:
        raise HTTPException(status_code=404, detail="Estanque no encontrado")
    return estanque

@router.put("/{estanque_id}", response_model=EstanqueOut)
def actualizar_estanque(estanque_id: int, data: EstanqueUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    estanque = db.query(Estanque).filter_by(estanque_id=estanque_id).first()
    if not estanque:
        raise HTTPException(status_code=404, detail="Estanque no encontrado")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(estanque, k, v)
    db.commit()
    db.refresh(estanque)
    return estanque

@router.delete("/{estanque_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_estanque(estanque_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    estanque = db.query(Estanque).filter_by(estanque_id=estanque_id).first()
    if not estanque:
        raise HTTPException(status_code=404, detail="Estanque no encontrado")
    db.delete(estanque)
    db.commit()
    return None
