# api/archivos.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from utils.db import get_db
from utils.dependencies import get_current_active_user

from models.archivo import Archivo, ArchivoProyeccion, ArchivoSiembraPlan, ArchivoPlanCosechas
from models.proyeccion import Proyeccion
from models.siembra import SiembraPlan
from models.plan_cosechas import PlanCosechas

from schemas.archivos import (
    ArchivoLinkCreate, ArchivoLinkOut,   # genérico: archivo_id, proposito, notas
)

router = APIRouter()

def ensure_archivo(db: Session, archivo_id: int) -> Archivo:
    obj = db.query(Archivo).get(archivo_id)
    if not obj: raise HTTPException(404, "Archivo no encontrado")
    return obj

# ---- Proyección
@router.get("/ciclos/{ciclo_id}/proyecciones/{proyeccion_id}/archivos", response_model=List[ArchivoLinkOut])
def list_archivos_proy(ciclo_id: int, proyeccion_id: int, db: Session = Depends(get_db), _=Depends(get_current_active_user)):
    proy = db.query(Proyeccion).filter(Proyeccion.proyeccion_id == proyeccion_id, Proyeccion.ciclo_id == ciclo_id).first()
    if not proy: raise HTTPException(404, "Proyección no encontrada")
    return proy.archivos

@router.post("/ciclos/{ciclo_id}/proyecciones/{proyeccion_id}/archivos", response_model=ArchivoLinkOut, status_code=201)
def link_archivo_proy(ciclo_id: int, proyeccion_id: int, data: ArchivoLinkCreate, db: Session = Depends(get_db), _=Depends(get_current_active_user)):
    proy = db.query(Proyeccion).filter(Proyeccion.proyeccion_id == proyeccion_id, Proyeccion.ciclo_id == ciclo_id).first()
    if not proy: raise HTTPException(404, "Proyección no encontrada")
    ensure_archivo(db, data.archivo_id)
    link = ArchivoProyeccion(proyeccion_id=proyeccion_id, **data.model_dump(exclude_unset=True))
    db.add(link); db.commit(); db.refresh(link)
    return link

# ---- Siembra plan
@router.get("/ciclos/{ciclo_id}/siembra/planes/{plan_id}/archivos", response_model=List[ArchivoLinkOut])
def list_archivos_sp(ciclo_id: int, plan_id: int, db: Session = Depends(get_db), _=Depends(get_current_active_user)):
    plan = db.query(SiembraPlan).filter(SiembraPlan.siembra_plan_id == plan_id, SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan: raise HTTPException(404, "Plan de siembra no encontrado")
    return plan.archivos

@router.post("/ciclos/{ciclo_id}/siembra/planes/{plan_id}/archivos", response_model=ArchivoLinkOut, status_code=201)
def link_archivo_sp(ciclo_id: int, plan_id: int, data: ArchivoLinkCreate, db: Session = Depends(get_db), _=Depends(get_current_active_user)):
    plan = db.query(SiembraPlan).filter(SiembraPlan.siembra_plan_id == plan_id, SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan: raise HTTPException(404, "Plan de siembra no encontrado")
    ensure_archivo(db, data.archivo_id)
    link = ArchivoSiembraPlan(siembra_plan_id=plan_id, **data.model_dump(exclude_unset=True))
    db.add(link); db.commit(); db.refresh(link)
    return link

# ---- Plan cosechas
@router.get("/ciclos/{ciclo_id}/cosecha/planes/{plan_id}/archivos", response_model=List[ArchivoLinkOut])
def list_archivos_pc(ciclo_id: int, plan_id: int, db: Session = Depends(get_db), _=Depends(get_current_active_user)):
    plan = db.query(PlanCosechas).filter(PlanCosechas.plan_cosechas_id == plan_id, PlanCosechas.ciclo_id == ciclo_id).first()
    if not plan: raise HTTPException(404, "Plan de cosechas no encontrado")
    return plan.archivos

@router.post("/ciclos/{ciclo_id}/cosecha/planes/{plan_id}/archivos", response_model=ArchivoLinkOut, status_code=201)
def link_archivo_pc(ciclo_id: int, plan_id: int, data: ArchivoLinkCreate, db: Session = Depends(get_db), _=Depends(get_current_active_user)):
    plan = db.query(PlanCosechas).filter(PlanCosechas.plan_cosechas_id == plan_id, PlanCosechas.ciclo_id == ciclo_id).first()
    if not plan: raise HTTPException(404, "Plan de cosechas no encontrado")
    ensure_archivo(db, data.archivo_id)
    link = ArchivoPlanCosechas(plan_cosechas_id=plan_id, **data.model_dump(exclude_unset=True))
    db.add(link); db.commit(); db.refresh(link)
    return link
