from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from utils.permissions import ensure_user_in_farm_or_admin
from schemas.farm import FarmCreate, FarmOut, FarmUpdate
from services.farm_service import list_farms, create_farm, update_farm
from models.user import Usuario

router = APIRouter(prefix="/farms", tags=["farms"])

@router.get("", response_model=list[FarmOut])
def get_farms(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    # Admin global ve todas; si no, podrías filtrar por usuario_granja.
    # Versión simple: todas (ajustaremos filtrado en iteración 2)
    return list_farms(db)

@router.post("", response_model=FarmOut)
def post_farm(payload: FarmCreate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    # Solo admin global crea granjas (puedes ampliar a roles)
    if not user.is_admin_global:
        # Si quieres atarlo a una granja específica, usa ensure_user_in_farm_or_admin
        # ensure_user_in_farm_or_admin(db, user.usuario_id, granja_id=?, is_admin_global=user.is_admin_global)
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admin global")
    return create_farm(db, payload)

@router.put("/{granja_id}", response_model=FarmOut)
def put_farm(granja_id: int, payload: FarmUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    if not user.is_admin_global:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admin global")
    return update_farm(db, granja_id, payload)
