# services/siembra_plan_service.py
from typing import Dict, Optional, List
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.usuario import Usuario
from models.ciclo import Ciclo
from models.estanque import Estanque
from models.siembra_plan import SiembraPlan
from models.siembra_estanque import SiembraEstanque

from enums.roles import Role
from enums.enums import CicloEstadoEnum, EstanqueStatusEnum, SiembraEstadoEnum
from utils.permissions import user_has_any_role, is_user_associated_to_granja


def _ensure_scope(db: Session, user: Usuario, granja_id: int, ciclo_id: int) -> Ciclo:
    if not user_has_any_role(user, [Role.admin_global]):
        if not is_user_associated_to_granja(db, user.usuario_id, granja_id):
            raise HTTPException(status_code=404, detail="granja_not_found: No existe o no tienes acceso.")
    ciclo = db.query(Ciclo).filter(Ciclo.ciclo_id == ciclo_id, Ciclo.granja_id == granja_id).first()
    if ciclo is None:
        raise HTTPException(status_code=404, detail="ciclo_not_found: No existe o no tienes acceso.")
    return ciclo


def _validar_ventana_en_ciclo(ciclo: Ciclo, ventana_inicio: date, ventana_fin: date) -> None:
    if ventana_fin < ventana_inicio:
        raise HTTPException(status_code=422, detail="date_range_invalid: ventana_fin < ventana_inicio.")
    if ventana_inicio < ciclo.fecha_inicio:
        raise HTTPException(status_code=422, detail="plan_window_out_of_cycle: ventana_inicio < fecha_inicio del ciclo.")
    if ciclo.fecha_fin_planificada and ventana_fin > ciclo.fecha_fin_planificada:
        raise HTTPException(status_code=422, detail="plan_window_out_of_cycle: ventana_fin > fecha_fin_planificada del ciclo.")


def _validar_unico_plan(db: Session, ciclo_id: int) -> None:
    exists = db.query(SiembraPlan.siembra_plan_id).filter(SiembraPlan.ciclo_id == ciclo_id).first() is not None
    if exists:
        raise HTTPException(status_code=409, detail="seeding_plan_exists: El ciclo ya tiene un plan de siembras.")


def _validar_ciclo_activo_para_mutar(ciclo: Ciclo) -> None:
    if ciclo.estado != CicloEstadoEnum.a:
        raise HTTPException(status_code=409, detail="cycle_not_active: Solo puedes crear/editar plan en un ciclo activo.")


def _validar_no_dependencias_para_borrar(db: Session, siembra_plan_id: int) -> None:
    hay_siembras = db.query(SiembraEstanque.siembra_estanque_id)\
                     .filter(SiembraEstanque.siembra_plan_id == siembra_plan_id)\
                     .first() is not None
    if hay_siembras:
        raise HTTPException(status_code=409, detail="plan_in_use: Existen siembras por estanque en el plan; no puedes eliminarlo.")


def get_plan_or_404(db: Session, user: Usuario, granja_id: int, ciclo_id: int) -> SiembraPlan:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    obj = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="seeding_plan_not_found: El ciclo no tiene plan de siembras.")
    return obj


def create_plan(db: Session, user: Usuario, granja_id: int, ciclo_id: int, data: Dict) -> SiembraPlan:
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo_para_mutar(ciclo)

    data.pop("ciclo_id", None)
    data.pop("created_by", None)

    _validar_unico_plan(db, ciclo_id)
    _validar_ventana_en_ciclo(ciclo=ciclo, ventana_inicio=data["ventana_inicio"], ventana_fin=data["ventana_fin"])

    plan = SiembraPlan(**data, ciclo_id=ciclo_id)
    if hasattr(plan, "created_by"):
        plan.created_by = user.usuario_id

    db.add(plan)
    db.commit()
    db.refresh(plan)

    # Auto-crear siembras para estanques ACTIVOS
    activos: List[Estanque] = (
        db.query(Estanque)
          .filter(Estanque.granja_id == granja_id, Estanque.status == EstanqueStatusEnum.a)
          .all()
    )

    if activos:
        existentes = {
            s.estanque_id
            for s in db.query(SiembraEstanque.estanque_id)
                       .filter(SiembraEstanque.siembra_plan_id == plan.siembra_plan_id)
                       .all()
        }
        nuevas: List[SiembraEstanque] = []
        for est in activos:
            if est.estanque_id in existentes:
                continue
            obj = SiembraEstanque(
                siembra_plan_id=plan.siembra_plan_id,
                estanque_id=est.estanque_id,
                estado=SiembraEstadoEnum.p,
                fecha_tentativa=plan.ventana_inicio,
            )
            if hasattr(obj, "created_by"):
                obj.created_by = user.usuario_id
            nuevas.append(obj)
        if nuevas:
            db.add_all(nuevas)
            db.commit()

    return plan


def update_plan(db: Session, user: Usuario, granja_id: int, ciclo_id: int, changes: Dict) -> SiembraPlan:
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo_para_mutar(ciclo)

    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="seeding_plan_not_found: El ciclo no tiene plan de siembras.")

    changes.pop("ciclo_id", None)
    changes.pop("created_by", None)

    v_ini = changes.get("ventana_inicio", plan.ventana_inicio)
    v_fin = changes.get("ventana_fin", plan.ventana_fin)
    _validar_ventana_en_ciclo(ciclo=ciclo, ventana_inicio=v_ini, ventana_fin=v_fin)

    for k, v in changes.items():
        setattr(plan, k, v)

    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def delete_plan(db: Session, user: Usuario, granja_id: int, ciclo_id: int) -> None:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="seeding_plan_not_found: El ciclo no tiene plan de siembras.")
    _validar_no_dependencias_para_borrar(db, plan.siembra_plan_id)
    db.delete(plan)
    db.commit()


# ---- NUEVO: SYNC para crear siembras faltantes cuando cambian estanques ----

def sync_siembras_faltantes(db: Session, user: Usuario, granja_id: int, ciclo_id: int) -> int:
    """Crea siembras faltantes para estanques ACTIVOS que no las tengan en el plan."""
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo_para_mutar(ciclo)

    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        raise HTTPException(status_code=409, detail="seeding_plan_missing: El ciclo no tiene plan de siembras.")

    activos = {
        e.estanque_id
        for e in db.query(Estanque).filter(
            Estanque.granja_id == granja_id, Estanque.status == EstanqueStatusEnum.a
        ).all()
    }
    ya = {
        s.estanque_id
        for s in db.query(SiembraEstanque).filter(
            SiembraEstanque.siembra_plan_id == plan.siembra_plan_id
        ).all()
    }

    faltantes = list(activos - ya)
    if not faltantes:
        return 0

    nuevos: List[SiembraEstanque] = []
    for est_id in faltantes:
        obj = SiembraEstanque(
            siembra_plan_id=plan.siembra_plan_id,
            estanque_id=est_id,
            estado=SiembraEstadoEnum.p,
            fecha_tentativa=plan.ventana_inicio,
        )
        if hasattr(obj, "created_by"):
            obj.created_by = user.usuario_id
        nuevos.append(obj)

    db.add_all(nuevos)
    db.commit()
    return len(nuevos)
