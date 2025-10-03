from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_active_user
from models.plan_cosechas import PlanCosechas
from schemas.plan_cosechas import PlanCosechasOut, PlanCosechasCreate, PlanCosechasUpdate

router = APIRouter(prefix="/planes-cosecha", tags=["planes-cosecha"])

@router.post("/", response_model=PlanCosechasOut)
def crear_plan_cosechas(data: PlanCosechasCreate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = PlanCosechas(**data.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/", response_model=list[PlanCosechasOut])
def listar_planes(
    ciclo_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_active_user),
):
    q = db.query(PlanCosechas)
    if ciclo_id:
        q = q.filter(PlanCosechas.ciclo_id == ciclo_id)
    return q.all()

@router.get("/{plan_cosechas_id}", response_model=PlanCosechasOut)
def obtener_plan(plan_cosechas_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(PlanCosechas).filter_by(plan_cosechas_id=plan_cosechas_id).first()
    if not obj:
        raise HTTPException(404, "Plan de cosechas no encontrado")
    return obj

@router.put("/{plan_cosechas_id}", response_model=PlanCosechasOut)
def actualizar_plan(plan_cosechas_id: int, data: PlanCosechasUpdate, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(PlanCosechas).filter_by(plan_cosechas_id=plan_cosechas_id).first()
    if not obj:
        raise HTTPException(404, "Plan de cosechas no encontrado")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/{plan_cosechas_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_plan(plan_cosechas_id: int, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    obj = db.query(PlanCosechas).filter_by(plan_cosechas_id=plan_cosechas_id).first()
    if not obj:
        raise HTTPException(404, "Plan de cosechas no encontrado")
    db.delete(obj)
    db.commit()
    return None
