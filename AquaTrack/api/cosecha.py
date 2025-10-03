from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_active_user
from models.cosecha import CosechaOla, CosechaEstanque
from schemas.cosecha import (
    CosechaOlaOut, CosechaOlaCreate, CosechaOlaUpdate,
    CosechaEstanqueOut, CosechaEstanqueCreate, CosechaEstanqueUpdate
)

router = APIRouter(prefix="/cosechas", tags=["cosechas"])

# --- CosechaOla ---
@router.post("/olas", response_model=CosechaOlaOut)
def crear_ola(data: CosechaOlaCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = CosechaOla(**data.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/olas", response_model=list[CosechaOlaOut])
def listar_olas(
    plan_cosechas_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_active_user),
):
    q = db.query(CosechaOla)
    if plan_cosechas_id:
        q = q.filter(CosechaOla.plan_cosechas_id == plan_cosechas_id)
    return q.all()

@router.get("/olas/{cosecha_ola_id}", response_model=CosechaOlaOut)
def obtener_ola(cosecha_ola_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(CosechaOla).filter_by(cosecha_ola_id=cosecha_ola_id).first()
    if not obj:
        raise HTTPException(404, "Ola no encontrada")
    return obj

@router.put("/olas/{cosecha_ola_id}", response_model=CosechaOlaOut)
def actualizar_ola(cosecha_ola_id: int, data: CosechaOlaUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(CosechaOla).filter_by(cosecha_ola_id=cosecha_ola_id).first()
    if not obj:
        raise HTTPException(404, "Ola no encontrada")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/olas/{cosecha_ola_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_ola(cosecha_ola_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(CosechaOla).filter_by(cosecha_ola_id=cosecha_ola_id).first()
    if not obj:
        raise HTTPException(404, "Ola no encontrada")
    db.delete(obj)
    db.commit()
    return None

# --- CosechaEstanque ---
@router.post("/estanques", response_model=CosechaEstanqueOut)
def crear_cosecha_estanque(data: CosechaEstanqueCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = CosechaEstanque(**data.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/estanques", response_model=list[CosechaEstanqueOut])
def listar_cosechas_estanque(
    estanque_id: int | None = Query(default=None),
    cosecha_ola_id: int | None = Query(default=None),
    estado: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_active_user),
):
    q = db.query(CosechaEstanque)
    if estanque_id:
        q = q.filter(CosechaEstanque.estanque_id == estanque_id)
    if cosecha_ola_id:
        q = q.filter(CosechaEstanque.cosecha_ola_id == cosecha_ola_id)
    if estado:
        q = q.filter(CosechaEstanque.estado == estado)
    return q.all()

@router.get("/estanques/{cosecha_estanque_id}", response_model=CosechaEstanqueOut)
def obtener_cosecha_estanque(cosecha_estanque_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(CosechaEstanque).filter_by(cosecha_estanque_id=cosecha_estanque_id).first()
    if not obj:
        raise HTTPException(404, "CosechaEstanque no encontrada")
    return obj

@router.put("/estanques/{cosecha_estanque_id}", response_model=CosechaEstanqueOut)
def actualizar_cosecha_estanque(cosecha_estanque_id: int, data: CosechaEstanqueUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(CosechaEstanque).filter_by(cosecha_estanque_id=cosecha_estanque_id).first()
    if not obj:
        raise HTTPException(404, "CosechaEstanque no encontrada")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/estanques/{cosecha_estanque_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_cosecha_estanque(cosecha_estanque_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(CosechaEstanque).filter_by(cosecha_estanque_id=cosecha_estanque_id).first()
    if not obj:
        raise HTTPException(404, "CosechaEstanque no encontrada")
    db.delete(obj)
    db.commit()
    return None
