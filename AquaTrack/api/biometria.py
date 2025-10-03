from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_active_user
from models.biometria import Biometria
from schemas.biometria import BiometriaOut, BiometriaCreate, BiometriaUpdate

router = APIRouter(prefix="/biometrias", tags=["biometrias"])

@router.post("/", response_model=BiometriaOut)
def crear_biometria(data: BiometriaCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = Biometria(**data.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/", response_model=list[BiometriaOut])
def listar_biometrias(
    ciclo_id: int | None = Query(default=None),
    estanque_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_active_user),
):
    q = db.query(Biometria)
    if ciclo_id:
        q = q.filter(Biometria.ciclo_id == ciclo_id)
    if estanque_id:
        q = q.filter(Biometria.estanque_id == estanque_id)
    return q.all()

@router.get("/{biometria_id}", response_model=BiometriaOut)
def obtener_biometria(biometria_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(Biometria).filter_by(biometria_id=biometria_id).first()
    if not obj:
        raise HTTPException(404, "Biometría no encontrada")
    return obj

@router.put("/{biometria_id}", response_model=BiometriaOut)
def actualizar_biometria(biometria_id: int, data: BiometriaUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(Biometria).filter_by(biometria_id=biometria_id).first()
    if not obj:
        raise HTTPException(404, "Biometría no encontrada")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/{biometria_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_biometria(biometria_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(Biometria).filter_by(biometria_id=biometria_id).first()
    if not obj:
        raise HTTPException(404, "Biometría no encontrada")
    db.delete(obj)
    db.commit()
    return None
