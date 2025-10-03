from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_active_user
from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from schemas.proyeccion import (
    ProyeccionOut, ProyeccionCreate, ProyeccionUpdate,
    ProyeccionLineaOut, ProyeccionLineaCreate, ProyeccionLineaUpdate
)

router = APIRouter(prefix="/proyecciones", tags=["proyecciones"])

# --- Proyeccion ---
@router.post("/", response_model=ProyeccionOut)
def crear_proyeccion(data: ProyeccionCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = Proyeccion(**data.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/", response_model=list[ProyeccionOut])
def listar_proyecciones(
    ciclo_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_active_user),
):
    q = db.query(Proyeccion)
    if ciclo_id:
        q = q.filter(Proyeccion.ciclo_id == ciclo_id)
    return q.all()

@router.get("/{proyeccion_id}", response_model=ProyeccionOut)
def obtener_proyeccion(proyeccion_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(Proyeccion).filter_by(proyeccion_id=proyeccion_id).first()
    if not obj:
        raise HTTPException(404, "Proyección no encontrada")
    return obj

@router.put("/{proyeccion_id}", response_model=ProyeccionOut)
def actualizar_proyeccion(proyeccion_id: int, data: ProyeccionUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(Proyeccion).filter_by(proyeccion_id=proyeccion_id).first()
    if not obj:
        raise HTTPException(404, "Proyección no encontrada")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/{proyeccion_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_proyeccion(proyeccion_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(Proyeccion).filter_by(proyeccion_id=proyeccion_id).first()
    if not obj:
        raise HTTPException(404, "Proyección no encontrada")
    db.delete(obj)
    db.commit()
    return None

# --- ProyeccionLinea ---
@router.post("/{proyeccion_id}/lineas", response_model=ProyeccionLineaOut)
def crear_linea(proyeccion_id: int, data: ProyeccionLineaCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    if proyeccion_id != data.proyeccion_id:
        raise HTTPException(400, "proyeccion_id inconsistente")
    obj = ProyeccionLinea(**data.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/{proyeccion_id}/lineas", response_model=list[ProyeccionLineaOut])
def listar_lineas(proyeccion_id: int, semana_idx: int | None = Query(default=None), db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    q = db.query(ProyeccionLinea).filter_by(proyeccion_id=proyeccion_id)
    if semana_idx is not None:
        q = q.filter(ProyeccionLinea.semana_idx == semana_idx)
    return q.all()

@router.get("/lineas/{linea_id}", response_model=ProyeccionLineaOut)
def obtener_linea(linea_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(ProyeccionLinea).filter_by(proyeccion_linea_id=linea_id).first()
    if not obj:
        raise HTTPException(404, "Línea de proyección no encontrada")
    return obj

@router.put("/lineas/{linea_id}", response_model=ProyeccionLineaOut)
def actualizar_linea(linea_id: int, data: ProyeccionLineaUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(ProyeccionLinea).filter_by(proyeccion_linea_id=linea_id).first()
    if not obj:
        raise HTTPException(404, "Línea de proyección no encontrada")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/lineas/{linea_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_linea(linea_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(ProyeccionLinea).filter_by(proyeccion_linea_id=linea_id).first()
    if not obj:
        raise HTTPException(404, "Línea de proyección no encontrada")
    db.delete(obj)
    db.commit()
    return None
