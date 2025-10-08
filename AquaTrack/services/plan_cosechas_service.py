# services/plan_cosechas_service.py
from __future__ import annotations
from typing import Dict, Optional, Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.usuario import Usuario
from models.ciclo import Ciclo
from models.plan_cosechas import PlanCosechas
from models.cosecha_ola import CosechaOla
from models.cosecha_estanque import CosechaEstanque

from enums.roles import Role
from enums.enums import CicloEstadoEnum
from utils.permissions import user_has_any_role, is_user_associated_to_granja
from services._proy_integration import proy_touch_borrador_event


def _ensure_scope(db: Session, user: Usuario, granja_id: int, ciclo_id: int) -> Ciclo:
    if not user_has_any_role(user, [Role.admin_global]):
        if not is_user_associated_to_granja(db, user.usuario_id, granja_id):
            raise HTTPException(status_code=404, detail="granja_not_found: No existe o no tienes acceso.")
    ciclo = db.query(Ciclo).filter(Ciclo.ciclo_id == ciclo_id, Ciclo.granja_id == granja_id).first()
    if ciclo is None:
        raise HTTPException(status_code=404, detail="ciclo_not_found: No existe o no tienes acceso.")
    return ciclo


def _validar_ciclo_activo(ciclo: Ciclo) -> None:
    if ciclo.estado != CicloEstadoEnum.a:
        raise HTTPException(status_code=409, detail="cycle_not_active: El ciclo no está activo.")


def _validar_unico_plan(db: Session, ciclo_id: int) -> None:
    exists = db.query(PlanCosechas.plan_cosechas_id).filter(PlanCosechas.ciclo_id == ciclo_id).first()
    if exists:
        raise HTTPException(status_code=409, detail="harvest_plan_exists: El ciclo ya tiene un plan de cosechas.")


def _ensure_plan_or_404(db: Session, ciclo_id: int) -> PlanCosechas:
    plan = db.query(PlanCosechas).filter(PlanCosechas.ciclo_id == ciclo_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="harvest_plan_not_found: El ciclo no tiene plan de cosechas.")
    return plan


def get_plan_or_404(db: Session, user: Usuario, granja_id: int, ciclo_id: int) -> PlanCosechas:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    return _ensure_plan_or_404(db, ciclo_id)


def create_plan(db: Session, user: Usuario, granja_id: int, ciclo_id: int, data: Dict) -> Tuple[PlanCosechas, Optional[int]]:
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)

    data.pop("ciclo_id", None)
    data.pop("created_by", None)

    _validar_unico_plan(db, ciclo_id)

    plan = PlanCosechas(**data, ciclo_id=ciclo_id)
    if hasattr(plan, "created_by"):
        plan.created_by = user.usuario_id

    db.add(plan)
    db.commit()
    db.refresh(plan)

    proy_id = proy_touch_borrador_event(
        db, ciclo_id=ciclo_id, actor_id=user.usuario_id, event="plan_cosecha:create", payload={"plan_id": plan.plan_cosechas_id}
    )
    return plan, proy_id


def update_plan(db: Session, user: Usuario, granja_id: int, ciclo_id: int, changes: Dict) -> Tuple[PlanCosechas, Optional[int]]:
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)

    plan = _ensure_plan_or_404(db, ciclo_id)

    for key in ("ciclo_id", "created_by", "created_at", "updated_at"):
        changes.pop(key, None)

    for k, v in changes.items():
        setattr(plan, k, v)

    db.add(plan)
    db.commit()
    db.refresh(plan)

    proy_id = proy_touch_borrador_event(
        db, ciclo_id=ciclo_id, actor_id=user.usuario_id, event="plan_cosecha:update", payload={"plan_id": plan.plan_cosechas_id}
    )
    return plan, proy_id


def _validar_no_dependencias_para_borrar(db: Session, plan_id: int) -> None:
    hay_olas = db.query(CosechaOla.cosecha_ola_id).filter(CosechaOla.plan_cosechas_id == plan_id).first() is not None
    if hay_olas:
        raise HTTPException(status_code=409, detail="plan_in_use: Existen olas de cosecha en el plan; no puedes eliminarlo.")


def delete_plan(db: Session, user: Usuario, granja_id: int, ciclo_id: int) -> Optional[int]:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    plan = _ensure_plan_or_404(db, ciclo_id)

    _validar_no_dependencias_para_borrar(db, plan.plan_cosechas_id)

    db.delete(plan)
    db.commit()

    proy_id = proy_touch_borrador_event(
        db, ciclo_id=ciclo_id, actor_id=user.usuario_id, event="plan_cosecha:delete", payload={"plan_id": plan.plan_cosechas_id}
    )
    return proy_id
