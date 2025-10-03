from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_active_user
from models.siembra import SiembraPlan, SiembraEstanque
from schemas.siembra import (
    SiembraPlanOut, SiembraPlanCreate, SiembraPlanUpdate,
    SiembraEstanqueOut, SiembraEstanqueCreate, SiembraEstanqueUpdate
)

router = APIRouter(prefix="/siembra", tags=["siembra"])

# --- SiembraPlan ---
@router.post("/planes", response_model=SiembraPlanOut)
def crear_siembra_plan(data: SiembraPlanCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = SiembraPlan(**data.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/planes", response_model=list[SiembraPlanOut])
def listar_siembra_planes(
    ciclo_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_active_user),
):
    q = db.query(SiembraPlan)
    if ciclo_id:
        q = q.filter(SiembraPlan.ciclo_id == ciclo_id)
    return q.all()

@router.get("/planes/{siembra_plan_id}", response_model=SiembraPlanOut)
def obtener_siembra_plan(siembra_plan_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(SiembraPlan).filter_by(siembra_plan_id=siembra_plan_id).first()
    if not obj:
        raise HTTPException(404, "SiembraPlan no encontrado")
    return obj

@router.put("/planes/{siembra_plan_id}", response_model=SiembraPlanOut)
def actualizar_siembra_plan(siembra_plan_id: int, data: SiembraPlanUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(SiembraPlan).filter_by(siembra_plan_id=siembra_plan_id).first()
    if not obj:
        raise HTTPException(404, "SiembraPlan no encontrado")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/planes/{siembra_plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_siembra_plan(siembra_plan_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(SiembraPlan).filter_by(siembra_plan_id=siembra_plan_id).first()
    if not obj:
        raise HTTPException(404, "SiembraPlan no encontrado")
    db.delete(obj)
    db.commit()
    return None

# --- SiembraEstanque ---
@router.post("/estanques", response_model=SiembraEstanqueOut)
def crear_siembra_estanque(data: SiembraEstanqueCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = SiembraEstanque(**data.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/estanques", response_model=list[SiembraEstanqueOut])
def listar_siembra_estanques(
    siembra_plan_id: int | None = Query(default=None),
    estanque_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_active_user)
):
    q = db.query(SiembraEstanque)
    if siembra_plan_id:
        q = q.filter(SiembraEstanque.siembra_plan_id == siembra_plan_id)
    if estanque_id:
        q = q.filter(SiembraEstanque.estanque_id == estanque_id)
    return q.all()

@router.get("/estanques/{siembra_estanque_id}", response_model=SiembraEstanqueOut)
def obtener_siembra_estanque(siembra_estanque_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(SiembraEstanque).filter_by(siembra_estanque_id=siembra_estanque_id).first()
    if not obj:
        raise HTTPException(404, "SiembraEstanque no encontrado")
    return obj

@router.put("/estanques/{siembra_estanque_id}", response_model=SiembraEstanqueOut)
def actualizar_siembra_estanque(siembra_estanque_id: int, data: SiembraEstanqueUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(SiembraEstanque).filter_by(siembra_estanque_id=siembra_estanque_id).first()
    if not obj:
        raise HTTPException(404, "SiembraEstanque no encontrado")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/estanques/{siembra_estanque_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_siembra_estanque(siembra_estanque_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(SiembraEstanque).filter_by(siembra_estanque_id=siembra_estanque_id).first()
    if not obj:
        raise HTTPException(404, "SiembraEstanque no encontrado")
    db.delete(obj)
    db.commit()
    return None
