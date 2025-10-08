# api/plan_cosechas.py
from typing import Dict, Any
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session

from utils.dependencies import get_db, get_current_user
from utils.permissions import ensure_roles, ensure_visibility_granja
from enums.roles import Role
from services import plan_cosechas_service
from schemas.plan_cosechas import PlanCosechasCreate, PlanCosechasUpdate, PlanCosechasOut
from models.usuario import Usuario
from config.settings import settings

router = APIRouter(
    prefix="/granjas/{granja_id}/ciclos/{ciclo_id}/cosecha-plan",
    tags=["Cosechas - Plan"],
)

@router.get("", response_model=PlanCosechasOut, status_code=status.HTTP_200_OK)
def get_plan(granja_id: int, ciclo_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    obj = plan_cosechas_service.get_plan_or_404(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id)
    return PlanCosechasOut.model_validate(obj)

@router.post("", response_model=PlanCosechasOut, status_code=status.HTTP_201_CREATED)
def create_plan(granja_id: int, ciclo_id: int, payload: PlanCosechasCreate, response: Response, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj, proy_id = plan_cosechas_service.create_plan(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, data=payload.model_dump())
    if proy_id and getattr(settings, "PROYECCION_EMIT_HEADERS", True):
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return PlanCosechasOut.model_validate(obj)

@router.patch("", response_model=PlanCosechasOut, status_code=status.HTTP_200_OK)
def update_plan(granja_id: int, ciclo_id: int, payload: PlanCosechasUpdate, response: Response, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj, proy_id = plan_cosechas_service.update_plan(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, changes=payload.model_dump(exclude_unset=True))
    if proy_id and getattr(settings, "PROYECCION_EMIT_HEADERS", True):
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return PlanCosechasOut.model_validate(obj)

@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(granja_id: int, ciclo_id: int, response: Response, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    ensure_roles(current_user, [Role.admin_global])
    ensure_visibility_granja(db, current_user, granja_id)
    proy_id = plan_cosechas_service.delete_plan(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id)
    if proy_id and getattr(settings, "PROYECCION_EMIT_HEADERS", True):
        response.headers["X-Proyeccion-Borrador-Id"] = str(proy_id)
    return None
