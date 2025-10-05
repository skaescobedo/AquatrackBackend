# api/siembra_plan.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from utils.dependencies import get_db, get_current_user
from utils.permissions import ensure_roles, ensure_visibility_granja
from enums.roles import Role
from services import siembra_plan_service
from schemas.siembra_plan import SiembraPlanCreate, SiembraPlanUpdate, SiembraPlanOut
from models.usuario import Usuario

router = APIRouter(
    prefix="/granjas/{granja_id}/ciclos/{ciclo_id}/siembra-plan",
    tags=["Siembras - Plan"]
)

@router.get("", response_model=SiembraPlanOut, status_code=status.HTTP_200_OK)
def get_plan(granja_id: int, ciclo_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    obj = siembra_plan_service.get_plan_or_404(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id)
    return SiembraPlanOut.model_validate(obj)

@router.post("", response_model=SiembraPlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(granja_id: int, ciclo_id: int, payload: SiembraPlanCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj = siembra_plan_service.create_plan(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, data=payload.model_dump())
    return SiembraPlanOut.model_validate(obj)

@router.patch("", response_model=SiembraPlanOut, status_code=status.HTTP_200_OK)
def update_plan(granja_id: int, ciclo_id: int, payload: SiembraPlanUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    obj = siembra_plan_service.update_plan(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id, changes=payload.model_dump(exclude_unset=True))
    return SiembraPlanOut.model_validate(obj)

@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(granja_id: int, ciclo_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    ensure_roles(current_user, [Role.admin_global])
    ensure_visibility_granja(db, current_user, granja_id)
    siembra_plan_service.delete_plan(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id)
    return None

# ---- NUEVO: SYNC ----
@router.post("/sync", response_model=dict, status_code=status.HTTP_200_OK)
def sync_siembras(granja_id: int, ciclo_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    ensure_roles(current_user, [Role.admin_global, Role.admin_granja])
    ensure_visibility_granja(db, current_user, granja_id)
    n = siembra_plan_service.sync_siembras_faltantes(db=db, user=current_user, granja_id=granja_id, ciclo_id=ciclo_id)
    return {"created": n}
