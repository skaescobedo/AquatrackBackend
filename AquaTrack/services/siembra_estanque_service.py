# services/siembra_estanque_service.py
from typing import Dict, List, Optional, Tuple
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.usuario import Usuario
from models.ciclo import Ciclo
from models.estanque import Estanque
from models.siembra_plan import SiembraPlan
from models.siembra_estanque import SiembraEstanque
from models.siembra_fecha_log import SiembraFechaLog

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


def _ensure_plan_for_ciclo(db: Session, ciclo_id: int) -> SiembraPlan:
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        raise HTTPException(status_code=409, detail="seeding_plan_missing: El ciclo no tiene plan de siembras.")
    return plan


def _ensure_estanque_activo_y_de_granja(db: Session, estanque_id: int, granja_id: int) -> Estanque:
    est = db.query(Estanque).filter(Estanque.estanque_id == estanque_id, Estanque.granja_id == granja_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="estanque_not_found: El estanque no existe en esta granja.")
    if est.status != EstanqueStatusEnum.a:
        raise HTTPException(status_code=409, detail="pond_inactive: El estanque no está activo para siembras.")
    return est


def _validar_ciclo_activo(ciclo: Ciclo) -> None:
    if ciclo.estado != CicloEstadoEnum.a:
        raise HTTPException(status_code=409, detail="cycle_not_active: El ciclo no está activo.")


def _validar_fechas_en_ciclo(ciclo: Ciclo, fecha_tentativa: Optional[date], fecha_siembra: Optional[date]) -> None:
    if fecha_tentativa:
        if fecha_tentativa < ciclo.fecha_inicio:
            raise HTTPException(status_code=422, detail="sowing_date_out_of_cycle: fecha_tentativa < fecha_inicio del ciclo.")
        if ciclo.fecha_fin_planificada and fecha_tentativa > ciclo.fecha_fin_planificada:
            raise HTTPException(status_code=422, detail="sowing_date_out_of_cycle: fecha_tentativa > fecha_fin_planificada del ciclo.")
    if fecha_siembra:
        if fecha_siembra < ciclo.fecha_inicio:
            raise HTTPException(status_code=422, detail="sowing_date_out_of_cycle: fecha_siembra < fecha_inicio del ciclo.")
        if ciclo.fecha_fin_planificada and fecha_siembra > ciclo.fecha_fin_planificada:
            raise HTTPException(status_code=422, detail="sowing_date_out_of_cycle: fecha_siembra > fecha_fin_planificada del ciclo.")


def _validar_unica_por_plan_estanque(db: Session, siembra_plan_id: int, estanque_id: int) -> None:
    exists = (
        db.query(SiembraEstanque.siembra_estanque_id)
        .filter(SiembraEstanque.siembra_plan_id == siembra_plan_id, SiembraEstanque.estanque_id == estanque_id)
        .first()
        is not None
    )
    if exists:
        raise HTTPException(status_code=409, detail="sowing_exists: Ya existe una siembra para este estanque en el plan.")


def _cobertura_completa(db: Session, granja_id: int, plan: SiembraPlan) -> bool:
    activos = {
        e.estanque_id
        for e in db.query(Estanque).filter(Estanque.granja_id == plan.ciclo.granja_id, Estanque.status == EstanqueStatusEnum.a).all()
    }
    ya = {
        s.estanque_id
        for s in db.query(SiembraEstanque).filter(SiembraEstanque.siembra_plan_id == plan.siembra_plan_id).all()
    }
    return len(activos) > 0 and activos.issubset(ya)


# ---- Proyección de valores efectivos con nombres “planos” ----
def _apply_effective_fields(obj: SiembraEstanque, plan: SiembraPlan) -> None:
    """
    Proyecta:
      - obj.densidad_org_m2      (efectivo: override o plan)
      - obj.talla_inicial_g      (efectivo: override o plan)
    para que Pydantic (Out) los serialice.
    """
    obj.densidad_org_m2 = (
        obj.densidad_override_org_m2
        if obj.densidad_override_org_m2 is not None
        else plan.densidad_org_m2
    )
    obj.talla_inicial_g = (
        obj.talla_inicial_override_g
        if obj.talla_inicial_override_g is not None
        else plan.talla_inicial_g
    )


# ------ List / Get ------

def list_siembras(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    page: int,
    page_size: int,
    order_by: str,
    order: str,
    estado: Optional[SiembraEstadoEnum],
    estanque_id: Optional[int],
) -> Tuple[List[SiembraEstanque], int]:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    plan = _ensure_plan_for_ciclo(db, ciclo_id)

    q = db.query(SiembraEstanque).filter(SiembraEstanque.siembra_plan_id == plan.siembra_plan_id)
    if estado:
        q = q.filter(SiembraEstanque.estado == estado)
    if estanque_id:
        q = q.filter(SiembraEstanque.estanque_id == estanque_id)

    valid_order = {
        "fecha_tentativa": SiembraEstanque.fecha_tentativa,
        "fecha_siembra": SiembraEstanque.fecha_siembra,
        "created_at": SiembraEstanque.created_at,
    }
    col = valid_order.get(order_by, SiembraEstanque.created_at)
    q = q.order_by(col.asc() if order == "asc" else col.desc())

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()

    for it in items:
        _apply_effective_fields(it, plan)

    return items, total


def get_siembra(db: Session, user: Usuario, granja_id: int, ciclo_id: int, siembra_estanque_id: int) -> SiembraEstanque:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    plan = _ensure_plan_for_ciclo(db, ciclo_id)
    obj = (
        db.query(SiembraEstanque)
        .filter(SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
                SiembraEstanque.siembra_estanque_id == siembra_estanque_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="sowing_not_found: No existe o no tienes acceso.")

    _apply_effective_fields(obj, plan)
    return obj


# ------ Create (manual permitido SOLO si falta cobertura) ------

def create_siembra(db: Session, user: Usuario, granja_id: int, ciclo_id: int, data: Dict) -> SiembraEstanque:
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)

    plan = _ensure_plan_for_ciclo(db, ciclo_id)

    if _cobertura_completa(db, granja_id, plan):
        raise HTTPException(status_code=409, detail="sowing_coverage_complete: Todos los estanques activos ya tienen siembra.")

    data.pop("siembra_plan_id", None)
    data.pop("created_by", None)

    _ensure_estanque_activo_y_de_granja(db, data["estanque_id"], granja_id)
    _validar_unica_por_plan_estanque(db, plan.siembra_plan_id, data["estanque_id"])
    _validar_fechas_en_ciclo(ciclo, data.get("fecha_tentativa"), data.get("fecha_siembra"))

    obj = SiembraEstanque(**data, siembra_plan_id=plan.siembra_plan_id)
    if hasattr(obj, "created_by"):
        obj.created_by = user.usuario_id

    db.add(obj)
    db.commit()
    db.refresh(obj)

    _apply_effective_fields(obj, plan)
    return obj


# ------ Update (sin estado ni fecha_siembra) ------

def update_siembra(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    siembra_estanque_id: int,
    changes: Dict
) -> SiembraEstanque:
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)

    plan = _ensure_plan_for_ciclo(db, ciclo_id)
    obj = get_siembra(db, user, granja_id, ciclo_id, siembra_estanque_id)

    if obj.estado == SiembraEstadoEnum.f:
        raise HTTPException(status_code=409, detail="sowing_immutable: La siembra ya fue confirmada/finalizada.")

    if "estado" in changes or "fecha_siembra" in changes:
        raise HTTPException(
            status_code=422,
            detail="forbidden_fields_in_patch: 'estado' y 'fecha_siembra' solo pueden cambiarse en /confirmar."
        )

    for key in ("estanque_id", "siembra_plan_id", "created_by"):
        changes.pop(key, None)

    if "fecha_tentativa" in changes:
        just = changes.get("justificacion_cambio_fecha")
        if not just or not just.strip():
            raise HTTPException(status_code=422, detail="missing_justification: Se requiere justificación para cambiar fecha_tentativa.")
        nueva_t = changes.get("fecha_tentativa", obj.fecha_tentativa)
        _validar_fechas_en_ciclo(ciclo, nueva_t, obj.fecha_siembra)
    else:
        just = None

    old_t, old_r = obj.fecha_tentativa, obj.fecha_siembra

    for k, v in list(changes.items()):
        if k != "justificacion_cambio_fecha":
            setattr(obj, k, v)

    db.add(obj)
    db.commit()
    db.refresh(obj)

    if just and (old_t != obj.fecha_tentativa):
        log = SiembraFechaLog(
            siembra_estanque_id=siembra_estanque_id,
            fecha_anterior=old_t,
            fecha_nueva=obj.fecha_tentativa,
            motivo=just,  # tu justificación
            changed_by=getattr(user, "usuario_id", None),
        )
        db.add(log)
        db.commit()

    _apply_effective_fields(obj, plan)
    return obj


def delete_siembra(db: Session, user: Usuario, granja_id: int, ciclo_id: int, siembra_estanque_id: int) -> None:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    obj = get_siembra(db, user, granja_id, ciclo_id, siembra_estanque_id)
    if obj.estado != SiembraEstadoEnum.p:
        raise HTTPException(status_code=409, detail="sowing_locked: Solo puedes eliminar siembras en estado planeado.")
    db.delete(obj)
    db.commit()


# ------ Confirmar (finalizar e inmovilizar) ------

def confirm_siembra(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    siembra_estanque_id: int,
    *,
    fecha_siembra: date,
    observaciones: Optional[str] = None,
    justificacion: Optional[str] = None,
) -> SiembraEstanque:
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)
    plan = _ensure_plan_for_ciclo(db, ciclo_id)
    obj = get_siembra(db, user, granja_id, ciclo_id, siembra_estanque_id)

    if obj.estado == SiembraEstadoEnum.f:
        raise HTTPException(status_code=409, detail="sowing_already_finalized: Ya estaba finalizada.")

    _validar_fechas_en_ciclo(ciclo, obj.fecha_tentativa, fecha_siembra)

    old_t, old_r = obj.fecha_tentativa, obj.fecha_siembra

    obj.fecha_siembra = fecha_siembra
    obj.estado = SiembraEstadoEnum.f
    if hasattr(obj, "observaciones") and observaciones:
        obj.observaciones = (obj.observaciones + " | " if obj.observaciones else "") + str(observaciones)

    db.add(obj)
    db.commit()
    db.refresh(obj)

    # Usamos la misma estructura de log que en update (consistente con tu modelo)
    if old_r != obj.fecha_siembra or old_t != obj.fecha_tentativa:
        log = SiembraFechaLog(
            siembra_estanque_id=siembra_estanque_id,
            fecha_anterior=old_r,
            fecha_nueva=obj.fecha_siembra,
            motivo=justificacion or "confirmación de siembra (fecha real)",
            changed_by=getattr(user, "usuario_id", None),
        )
        db.add(log)
        db.commit()

    _apply_effective_fields(obj, plan)
    return obj
