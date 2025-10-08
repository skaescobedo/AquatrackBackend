# services/cosecha_estanque_service.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError  # <-- NUEVO

from models.usuario import Usuario
from models.ciclo import Ciclo
from models.estanque import Estanque
from models.plan_cosechas import PlanCosechas
from models.cosecha_ola import CosechaOla
from models.cosecha_estanque import CosechaEstanque
from models.cosecha_fecha_log import CosechaFechaLog
# NUEVO: para validar siembra confirmada
from models.siembra_plan import SiembraPlan
from models.siembra_estanque import SiembraEstanque

from enums.roles import Role
from enums.enums import (
    CicloEstadoEnum,
    CosechaEstadoDetEnum,
    EstanqueStatusEnum,
    SiembraEstadoEnum,  # nuevo
)
from utils.permissions import user_has_any_role, is_user_associated_to_granja
from services._proy_integration import proy_touch_borrador_event


# Helper pequeño para asegurar que tenemos user id
def _require_user_id(user: Usuario) -> int:
    uid = getattr(user, "usuario_id", None)
    if not uid:
        # si por alguna razón no hay usuario autenticado válido
        raise HTTPException(status_code=401, detail="auth_required: usuario inválido para auditoría")
    return uid

def _log_cambio_fecha_cosecha(
    db: Session,
    *,
    user: Usuario,
    cosecha_estanque_id: int,
    old_date: Optional[date],
    new_date: Optional[date],
    motivo: Optional[str],
) -> None:
    """Crea log solo si la fecha realmente cambió; siempre con changed_by."""
    if old_date == new_date:
        return
    log = CosechaFechaLog(
        cosecha_estanque_id=cosecha_estanque_id,
        fecha_anterior=old_date,
        fecha_nueva=new_date,
        motivo=motivo or "ajuste de fecha",
        changed_by=_require_user_id(user),   # <-- CLAVE
    )
    db.add(log)
    db.flush()  # atrapa NOT NULL / FK antes del commit

def _ensure_scope(db: Session, user: Usuario, granja_id: int, ciclo_id: int) -> Ciclo:
    if not user_has_any_role(user, [Role.admin_global]):
        if not is_user_associated_to_granja(db, user.usuario_id, granja_id):
            raise HTTPException(status_code=404, detail="granja_not_found: No existe o no tienes acceso.")
    ciclo = db.query(Ciclo).filter(Ciclo.ciclo_id == ciclo_id, Ciclo.granja_id == granja_id).first()
    if ciclo is None:
        raise HTTPException(status_code=404, detail="ciclo_not_found: No existe o no tienes acceso.")
    return ciclo


def _ensure_plan_y_ola(db: Session, ciclo_id: int, ola_id: int) -> CosechaOla:
    plan = db.query(PlanCosechas).filter(PlanCosechas.ciclo_id == ciclo_id).first()
    if not plan:
        raise HTTPException(status_code=409, detail="harvest_plan_missing: El ciclo no tiene plan de cosechas.")
    ola = db.query(CosechaOla).filter(
        CosechaOla.plan_cosechas_id == plan.plan_cosechas_id,
        CosechaOla.cosecha_ola_id == ola_id
    ).first()
    if not ola:
        raise HTTPException(status_code=404, detail="harvest_wave_not_found")
    return ola


def _validar_ciclo_activo(ciclo: Ciclo) -> None:
    if ciclo.estado != CicloEstadoEnum.a:
        raise HTTPException(status_code=409, detail="cycle_not_active: El ciclo no está activo.")


def _validar_fecha_en_ciclo(ciclo: Ciclo, fecha: date) -> None:
    if fecha < ciclo.fecha_inicio:
        raise HTTPException(status_code=422, detail="harvest_date_out_of_cycle: fecha < fecha_inicio del ciclo.")
    if ciclo.fecha_fin_planificada and fecha > ciclo.fecha_fin_planificada:
        raise HTTPException(status_code=422, detail="harvest_date_out_of_cycle: fecha > fecha_fin_planificada del ciclo.")


def _validar_fecha_en_ventana(ola: CosechaOla, fecha: date) -> None:
    if fecha < ola.ventana_inicio or fecha > ola.ventana_fin:
        raise HTTPException(status_code=422, detail="harvest_date_out_of_window: fecha fuera de la ventana de la ola.")

def _ensure_siembra_confirmada(db: Session, ciclo_id: int, estanque_id: int) -> None:
    """
    Verifica que exista una SiembraEstanque en estado 'finalizada' (SiembraEstadoEnum.f)
    para el mismo ciclo y estanque. Bloquea creación/confirmación de cosecha si no.
    """
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        raise HTTPException(status_code=422, detail="sowing_missing: No hay siembra confirmada para este estanque/ciclo.")
    hay = (
        db.query(SiembraEstanque.siembra_estanque_id)
          .filter(
              SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
              SiembraEstanque.estanque_id == estanque_id,
              SiembraEstanque.estado == SiembraEstadoEnum.f,
          )
          .first()
        is not None
    )
    if not hay:
        raise HTTPException(status_code=422, detail="sowing_not_confirmed: Se requiere siembra confirmada antes de cosechar.")

def list_cosechas(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    ola_id: int,
    page: int,
    page_size: int,
    order_by: str,
    order: str,
    estado: Optional[CosechaEstadoDetEnum],
    estanque_id: Optional[int],
) -> Tuple[List[CosechaEstanque], int]:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    ola = _ensure_plan_y_ola(db, ciclo_id, ola_id)

    q = db.query(CosechaEstanque).filter(CosechaEstanque.cosecha_ola_id == ola.cosecha_ola_id)
    if estado:
        q = q.filter(CosechaEstanque.estado == estado)
    if estanque_id:
        q = q.filter(CosechaEstanque.estanque_id == estanque_id)

    valid_order = {
        "fecha_cosecha": CosechaEstanque.fecha_cosecha,
        "created_at": CosechaEstanque.created_at,
    }
    col = valid_order.get(order_by, CosechaEstanque.created_at)
    q = q.order_by(col.asc() if order == "asc" else col.desc())

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def get_cosecha(db: Session, user: Usuario, granja_id: int, ciclo_id: int, ola_id: int, det_id: int) -> CosechaEstanque:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    ola = _ensure_plan_y_ola(db, ciclo_id, ola_id)
    obj = db.query(CosechaEstanque).filter(
        CosechaEstanque.cosecha_ola_id == ola.cosecha_ola_id,
        CosechaEstanque.cosecha_estanque_id == det_id
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="harvest_detail_not_found")
    return obj


def _ensure_estanque_de_granja(db: Session, estanque_id: int, granja_id: int) -> Estanque:
    est = db.query(Estanque).filter(Estanque.estanque_id == estanque_id, Estanque.granja_id == granja_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="estanque_not_found: El estanque no existe en esta granja.")
    return est


def create_cosecha(db: Session, user: Usuario, granja_id: int, ciclo_id: int, ola_id: int, data: Dict) -> Tuple[CosechaEstanque, Optional[int]]:
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)
    ola = _ensure_plan_y_ola(db, ciclo_id, ola_id)

    data.pop("cosecha_ola_id", None)
    data.pop("created_by", None)
    _ensure_estanque_de_granja(db, data["estanque_id"], granja_id)

    # Siembra confirmada previa
    _ensure_siembra_confirmada(db, ciclo_id, data["estanque_id"])

    fecha = data["fecha_cosecha"]
    _validar_fecha_en_ciclo(ciclo, fecha)
    _validar_fecha_en_ventana(ola, fecha)

    obj = CosechaEstanque(**data, cosecha_ola_id=ola.cosecha_ola_id)
    if hasattr(obj, "created_by"):
        obj.created_by = user.usuario_id

    db.add(obj)
    db.commit()
    db.refresh(obj)

    proy_id = proy_touch_borrador_event(
        db, ciclo_id=ciclo_id, actor_id=user.usuario_id, event="cosecha_estanque:create", payload={"detalle_id": obj.cosecha_estanque_id}
    )
    return obj, proy_id


def update_cosecha(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    ola_id: int,
    det_id: int,
    changes: Dict,
) -> Tuple[CosechaEstanque, Optional[int]]:
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)
    ola = _ensure_plan_y_ola(db, ciclo_id, ola_id)
    obj = get_cosecha(db, user, granja_id, ciclo_id, ola_id, det_id)

    for key in ("cosecha_ola_id", "estanque_id", "created_by", "created_at", "updated_at"):
        changes.pop(key, None)

    nueva_fecha = changes.get("fecha_cosecha", obj.fecha_cosecha)
    if nueva_fecha != obj.fecha_cosecha:
        # exigir justificación si cambia fecha
        just = changes.get("justificacion_cambio_fecha")
        if just is None or not str(just).strip():
            raise HTTPException(status_code=422, detail="missing_justification: Se requiere justificacion_cambio_fecha para cambiar fecha_cosecha.")
        _validar_fecha_en_ciclo(ciclo, nueva_fecha)
        _validar_fecha_en_ventana(ola, nueva_fecha)

    old_fecha = obj.fecha_cosecha

    for k, v in list(changes.items()):
        if k != "justificacion_cambio_fecha":
            setattr(obj, k, v)

    db.add(obj)
    # si cambió la fecha, genera el log antes del commit
    _log_cambio_fecha_cosecha(
        db,
        user=user,
        cosecha_estanque_id=obj.cosecha_estanque_id,
        old_date=old_fecha,
        new_date=obj.fecha_cosecha,
        motivo=changes.get("justificacion_cambio_fecha"),
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="harvest_update_failed: error de integridad (auditoría o FKs)")

    db.refresh(obj)

    proy_id = proy_touch_borrador_event(
        db, ciclo_id=ciclo_id, actor_id=user.usuario_id, event="cosecha_estanque:update",
        payload={"detalle_id": obj.cosecha_estanque_id}
    )
    return obj, proy_id


def confirm_cosecha(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    ola_id: int,
    det_id: int,
    *,
    fecha_cosecha: Optional[date] = None,
    pp_g: Optional[float] = None,
    biomasa_kg: Optional[float] = None,
    densidad_retirada_org_m2: Optional[float] = None,
    notas: Optional[str] = None,
    justificacion_cambio_fecha: Optional[str] = None,
) -> Tuple[CosechaEstanque, Optional[int]]:
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)
    ola = _ensure_plan_y_ola(db, ciclo_id, ola_id)
    obj = get_cosecha(db, user, granja_id, ciclo_id, ola_id, det_id)

    if obj.estado == CosechaEstadoDetEnum.c:
        # idempotencia básica: no reescribir; devolver 409
        raise HTTPException(status_code=409, detail="harvest_already_confirmed")

    # fecha real obligatoria
    new_fecha = fecha_cosecha or obj.fecha_cosecha
    if new_fecha is None:
        raise HTTPException(status_code=422, detail="harvest_real_date_required")

    _validar_fecha_en_ciclo(ciclo, new_fecha)
    _validar_fecha_en_ventana(ola, new_fecha)

    # siembra confirmada previa
    _ensure_siembra_confirmada(db, ciclo_id, obj.estanque_id)

    # métricas mínimas: biomasa_kg OR (pp_g AND densidad)
    tiene_biomasa = biomasa_kg is not None
    tiene_combo = (pp_g is not None) and (densidad_retirada_org_m2 is not None)
    if not (tiene_biomasa or tiene_combo):
        raise HTTPException(status_code=422, detail="harvest_metrics_min_missing: Requiere biomasa_kg o (pp_g y densidad_retirada_org_m2).")

    old_fecha = obj.fecha_cosecha

    obj.fecha_cosecha = new_fecha
    if pp_g is not None:
        obj.pp_g = pp_g
    if biomasa_kg is not None:
        obj.biomasa_kg = biomasa_kg
    if densidad_retirada_org_m2 is not None:
        obj.densidad_retirada_org_m2 = densidad_retirada_org_m2
    if notas:
        obj.notas = (obj.notas + " | " if obj.notas else "") + str(notas)

    obj.estado = CosechaEstadoDetEnum.c
    obj.confirmado_por = _require_user_id(user)  # <-- usa helper
    obj.confirmado_event_at = datetime.utcnow()

    db.add(obj)

    # Log de fecha si hubo cambio
    _log_cambio_fecha_cosecha(
        db,
        user=user,
        cosecha_estanque_id=obj.cosecha_estanque_id,
        old_date=old_fecha,
        new_date=obj.fecha_cosecha,
        motivo=(justificacion_cambio_fecha or "confirmación de cosecha (fecha real)"),
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="harvest_confirm_failed: error de integridad (auditoría o FKs)")

    db.refresh(obj)

    proy_id = proy_touch_borrador_event(
        db, ciclo_id=ciclo_id, actor_id=user.usuario_id, event="cosecha_estanque:confirm",
        payload={"detalle_id": obj.cosecha_estanque_id}
    )
    return obj, proy_id


def delete_cosecha(db: Session, user: Usuario, granja_id: int, ciclo_id: int, ola_id: int, det_id: int) -> Optional[int]:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    obj = get_cosecha(db, user, granja_id, ciclo_id, ola_id, det_id)
    if obj.estado != CosechaEstadoDetEnum.p:
        raise HTTPException(status_code=409, detail="harvest_locked: Solo puedes eliminar cosechas en estado pendiente.")
    db.delete(obj)
    db.commit()

    proy_id = proy_touch_borrador_event(
        db, ciclo_id=ciclo_id, actor_id=user.usuario_id, event="cosecha_estanque:delete", payload={"detalle_id": det_id}
    )
    return proy_id
