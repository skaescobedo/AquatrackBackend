from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_user
from models.usuario import Usuario
from schemas.harvest import PlanCosechasUpsert, PlanCosechasOut
from services.harvest_service import upsert_plan, get_plan

router = APIRouter(prefix="/cycles/{ciclo_id}/harvest/plan", tags=["harvest"])

@router.get("", response_model=PlanCosechasOut | None)
def get_plan_endpoint(
    ciclo_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    plan = get_plan(db, user, ciclo_id)
    if not plan:
        return None
    return {
        "plan_cosechas_id": plan.plan_cosechas_id,
        "ciclo_id": plan.ciclo_id,
        "nota_operativa": plan.nota_operativa,
    }

@router.post("", response_model=PlanCosechasOut)
def upsert_plan_endpoint(
    ciclo_id: int = Path(..., gt=0),
    body: PlanCosechasUpsert = ...,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    plan = upsert_plan(db, user, ciclo_id, body.nota_operativa)
    return {
        "plan_cosechas_id": plan.plan_cosechas_id,
        "ciclo_id": plan.ciclo_id,
        "nota_operativa": plan.nota_operativa,
    }
