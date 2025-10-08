# services/cosecha_ola_service.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.usuario import Usuario
from models.ciclo import Ciclo
from models.plan_cosechas import PlanCosechas
from models.cosecha_ola import CosechaOla
from models.cosecha_estanque import CosechaEstanque
from models.estanque import Estanque
# NUEVO: para filtrar por siembra confirmada
from models.siembra_plan import SiembraPlan
from models.siembra_estanque import SiembraEstanque

from enums.roles import Role
from enums.enums import CicloEstadoEnum, CosechaEstadoEnum, EstanqueStatusEnum, SiembraEstadoEnum
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


def _ensure_plan_or_404(db: Session, ciclo_id: int) -> PlanCosechas:
    plan = db.query(PlanCosechas).filter(PlanCosechas.ciclo_id == ciclo_id).first()
    if not plan:
        raise HTTPException(status_code=409, detail="harvest_plan_missing: El ciclo no tiene plan de cosechas.")
    return plan


def _validar_ciclo_activo(ciclo: Ciclo) -> None:
    if ciclo.estado != CicloEstadoEnum.a:
        raise HTTPException(status_code=409, detail="cycle_not_active: El ciclo no está activo.")


def _validar_ventana_en_ciclo(ciclo: Ciclo, ini: date, fin: date) -> None:
    if fin < ini:
        raise HTTPException(status_code=422, detail="date_range_invalid: ventana_fin < ventana_inicio.")
    if ini < ciclo.fecha_inicio:
        raise HTTPException(status_code=422, detail="window_out_of_cycle: ventana_inicio < fecha_inicio del ciclo.")
    if ciclo.fecha_fin_planificada and fin > ciclo.fecha_fin_planificada:
        raise HTTPException(status_code=422, detail="window_out_of_cycle: ventana_fin > fecha_fin_planificada del ciclo.")


def _estanques_con_siembra_confirmada(db: Session, granja_id: int, ciclo_id: int) -> List[int]:
    """
    Devuelve IDs de estanques ACTIVOS en la granja que tienen SiembraEstanque **finalizada**
    para el ciclo dado.
    """
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        return []
    # activos en granja
    activos = {
        e.estanque_id
        for e in db.query(Estanque).filter(Estanque.granja_id == granja_id, Estanque.status == EstanqueStatusEnum.a).all()
    }
    # con siembra finalizada en el plan
    confirmados = {
        s.estanque_id
        for s in db.query(SiembraEstanque).filter(
            SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
            SiembraEstanque.estado == SiembraEstadoEnum.f
        ).all()
    }
    return list(activos & confirmados)


def list_olas(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    page: int,
    page_size: int,
    order_by: str,
    order: str,
    estado: Optional[CosechaEstadoEnum],
) -> Tuple[List[CosechaOla], int]:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    plan = _ensure_plan_or_404(db, ciclo_id)

    q = db.query(CosechaOla).filter(CosechaOla.plan_cosechas_id == plan.plan_cosechas_id)
    if estado:
        q = q.filter(CosechaOla.estado == estado)

    valid_order = {
        "created_at": CosechaOla.created_at,
        "ventana_inicio": CosechaOla.ventana_inicio,
        "ventana_fin": CosechaOla.ventana_fin,
        "orden": CosechaOla.orden,
    }
    col = valid_order.get(order_by, CosechaOla.created_at)
    q = q.order_by(col.asc() if order == "asc" else col.desc())

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def get_ola(db: Session, user: Usuario, granja_id: int, ciclo_id: int, ola_id: int) -> CosechaOla:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    plan = _ensure_plan_or_404(db, ciclo_id)
    obj = db.query(CosechaOla).filter(
        CosechaOla.plan_cosechas_id == plan.plan_cosechas_id,
        CosechaOla.cosecha_ola_id == ola_id
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="harvest_wave_not_found")
    return obj


def create_ola(db: Session, user: Usuario, granja_id: int, ciclo_id: int, data: Dict) -> Tuple[CosechaOla, Optional[int]]:
    """
    Crea la ola y **auto-genera** CosechaEstanque para estanques con siembra **confirmada**
    usando como fecha inicial la `ventana_inicio` de la ola.
    """
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)
    plan = _ensure_plan_or_404(db, ciclo_id)

    data.pop("plan_cosechas_id", None)
    data.pop("created_by", None)

    ini = data["ventana_inicio"]
    fin = data["ventana_fin"]
    _validar_ventana_en_ciclo(ciclo, ini, fin)

    ola = CosechaOla(**data, plan_cosechas_id=plan.plan_cosechas_id)
    if hasattr(ola, "created_by"):
        ola.created_by = user.usuario_id

    db.add(ola)
    db.commit()
    db.refresh(ola)

    # --- Auto-seeding de detalles SOLO para estanques con siembra confirmada ---
    activos_ids = _estanques_con_siembra_confirmada(db, granja_id, ciclo_id)
    nuevos: List[CosechaEstanque] = []
    if activos_ids:
        for est_id in activos_ids:
            det = CosechaEstanque(
                estanque_id=est_id,
                cosecha_ola_id=ola.cosecha_ola_id,
                # estado usa default 'p'
                fecha_cosecha=ola.ventana_inicio,
            )
            if hasattr(det, "created_by"):
                det.created_by = user.usuario_id
            nuevos.append(det)

        db.add_all(nuevos)
        db.commit()

    proy_id = proy_touch_borrador_event(
        db,
        ciclo_id=ciclo_id,
        actor_id=user.usuario_id,
        event="cosecha_ola:create",
        payload={
            "ola_id": ola.cosecha_ola_id,
            "auto_detalles_creados": len(nuevos),
            "detalles_ids": [d.cosecha_estanque_id for d in nuevos] if nuevos else [],
        },
    )
    return ola, proy_id


def update_ola(db: Session, user: Usuario, granja_id: int, ciclo_id: int, ola_id: int, changes: Dict) -> Tuple[CosechaOla, Optional[int]]:
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)
    ola = get_ola(db, user, granja_id, ciclo_id, ola_id)

    for key in ("plan_cosechas_id", "created_by", "created_at", "updated_at"):
        changes.pop(key, None)

    ini = changes.get("ventana_inicio", ola.ventana_inicio)
    fin = changes.get("ventana_fin", ola.ventana_fin)
    _validar_ventana_en_ciclo(ciclo, ini, fin)

    for k, v in changes.items():
        setattr(ola, k, v)

    db.add(ola)
    db.commit()
    db.refresh(ola)

    proy_id = proy_touch_borrador_event(
        db, ciclo_id=ciclo_id, actor_id=user.usuario_id, event="cosecha_ola:update", payload={"ola_id": ola.cosecha_ola_id}
    )
    return ola, proy_id


def _validar_no_detalles_para_borrar(db: Session, ola_id: int) -> None:
    hay = db.query(CosechaEstanque.cosecha_estanque_id).filter(CosechaEstanque.cosecha_ola_id == ola_id).first() is not None
    if hay:
        raise HTTPException(status_code=409, detail="wave_in_use: Existen cosechas asociadas; no puedes eliminar la ola.")


def delete_ola(db: Session, user: Usuario, granja_id: int, ciclo_id: int, ola_id: int) -> Optional[int]:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    ola = get_ola(db, user, granja_id, ciclo_id, ola_id)
    _validar_no_detalles_para_borrar(db, ola_id)

    db.delete(ola)
    db.commit()

    proy_id = proy_touch_borrador_event(
        db, ciclo_id=ciclo_id, actor_id=user.usuario_id, event="cosecha_ola:delete", payload={"ola_id": ola_id}
    )
    return proy_id


# ---- SYNC para crear cosechas faltantes cuando cambian estanques ----
def sync_cosechas_faltantes(db: Session, user: Usuario, granja_id: int, ciclo_id: int, ola_id: int) -> Tuple[int, Optional[int]]:
    """
    Crea CosechaEstanque faltantes para estanques con siembra **confirmada** que no los tengan en la ola.
    """
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)
    ola = get_ola(db, user, granja_id, ciclo_id, ola_id)

    activos = set(_estanques_con_siembra_confirmada(db, granja_id, ciclo_id))
    ya = {
        d.estanque_id
        for d in db.query(CosechaEstanque).filter(CosechaEstanque.cosecha_ola_id == ola.cosecha_ola_id).all()
    }

    faltantes = list(activos - ya)
    if not faltantes:
        return 0, None

    nuevos: List[CosechaEstanque] = []
    for est_id in faltantes:
        det = CosechaEstanque(
            estanque_id=est_id,
            cosecha_ola_id=ola.cosecha_ola_id,
            fecha_cosecha=ola.ventana_inicio,
        )
        if hasattr(det, "created_by"):
            det.created_by = user.usuario_id
        nuevos.append(det)

    db.add_all(nuevos)
    db.commit()

    proy_id = proy_touch_borrador_event(
        db,
        ciclo_id=ciclo_id,
        actor_id=user.usuario_id,
        event="cosecha_ola:sync",
        payload={
            "ola_id": ola.cosecha_ola_id,
            "auto_detalles_creados": len(nuevos),
            "detalles_ids": [d.cosecha_estanque_id for d in nuevos],
        },
    )
    return len(nuevos), proy_id
