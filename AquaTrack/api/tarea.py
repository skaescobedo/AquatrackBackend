from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_active_user
from models.tarea import Tarea
from schemas.tarea import TareaOut, TareaCreate, TareaUpdate

router = APIRouter(prefix="/tareas", tags=["tareas"])

@router.post("/", response_model=TareaOut)
def crear_tarea(data: TareaCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = Tarea(**data.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/", response_model=list[TareaOut])
def listar_tareas(db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    return db.query(Tarea).all()

@router.get("/{tarea_id}", response_model=TareaOut)
def obtener_tarea(tarea_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(Tarea).filter_by(tarea_id=tarea_id).first()
    if not obj:
        raise HTTPException(404, "Tarea no encontrada")
    return obj

@router.put("/{tarea_id}", response_model=TareaOut)
def actualizar_tarea(tarea_id: int, data: TareaUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(Tarea).filter_by(tarea_id=tarea_id).first()
    if not obj:
        raise HTTPException(404, "Tarea no encontrada")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/{tarea_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_tarea(tarea_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(Tarea).filter_by(tarea_id=tarea_id).first()
    if not obj:
        raise HTTPException(404, "Tarea no encontrada")
    db.delete(obj)
    db.commit()
    return None
