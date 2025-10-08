# services/biometria_service.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.usuario import Usuario
from models.ciclo import Ciclo
from models.estanque import Estanque
from models.biometria import Biometria
from models.sob_cambio_log import SobCambioLog

from enums.roles import Role
from enums.enums import CicloEstadoEnum, EstanqueStatusEnum, SobFuenteEnum
from utils.permissions import user_has_any_role, is_user_associated_to_granja


# ----------------- Helpers de alcance/validación -----------------

def _ensure_scope(db: Session, user: Usuario, granja_id: int, ciclo_id: int) -> Ciclo:
    if not user_has_any_role(user, [Role.admin_global]):
        if not is_user_associated_to_granja(db, user.usuario_id, granja_id):
            raise HTTPException(status_code=404, detail="granja_not_found: No existe o no tienes acceso.")
    ciclo = db.query(Ciclo).filter(Ciclo.ciclo_id == ciclo_id, Ciclo.granja_id == granja_id).first()
    if not ciclo:
        raise HTTPException(status_code=404, detail="ciclo_not_found: No existe o no tienes acceso.")
    return ciclo


def _validar_ciclo_activo(ciclo: Ciclo) -> None:
    if ciclo.estado != CicloEstadoEnum.a:
        raise HTTPException(status_code=409, detail="cycle_not_active: El ciclo no está activo.")


def _ensure_estanque_de_granja_activo(db: Session, estanque_id: int, granja_id: int) -> Estanque:
    est = db.query(Estanque).filter(Estanque.estanque_id == estanque_id, Estanque.granja_id == granja_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="estanque_not_found: El estanque no existe en esta granja.")
    # Para biometrías podrías permitir también estanques no activos;
    # si quieres requerir activos, descomenta:
    # if est.status != EstanqueStatusEnum.a:
    #     raise HTTPException(status_code=409, detail="pond_inactive: El estanque no está activo.")
    return est


# ----------------- Helpers de SOB -----------------

def _sob_actual_pct(db: Session, estanque_id: int, ciclo_id: int) -> float:
    """
    Regresa el SOB vigente (último sob_nueva_pct). Si no hay registros, usa 100.0 por defecto.
    """
    row = (
        db.query(SobCambioLog)
        .filter(SobCambioLog.estanque_id == estanque_id, SobCambioLog.ciclo_id == ciclo_id)
        .order_by(SobCambioLog.changed_at.desc(), SobCambioLog.sob_cambio_log_id.desc())
        .first()
    )
    if row:
        return float(row.sob_nueva_pct)
    return 100.0


def _insert_sob_log(
    db: Session,
    *,
    estanque_id: int,
    ciclo_id: int,
    anterior_pct: float,
    nueva_pct: float,
    actor_id: Optional[int],
    fuente: SobFuenteEnum,
    motivo: Optional[str],
) -> SobCambioLog:
    log = SobCambioLog(
        estanque_id=estanque_id,
        ciclo_id=ciclo_id,
        sob_anterior_pct=anterior_pct,
        sob_nueva_pct=nueva_pct,
        fuente=fuente,
        motivo=motivo,
        changed_by=actor_id or 0,  # si por alguna razón no hay usuario, 0 evita NULL (FK debe existir si aplica)
    )
    db.add(log)
    # no commit aquí; el caller hace commit del batch
    return log


# ----------------- Queries de apoyo -----------------

def _ultima_biometria_previa(db: Session, ciclo_id: int, estanque_id: int, fecha: date) -> Optional[Biometria]:
    return (
        db.query(Biometria)
        .filter(
            Biometria.ciclo_id == ciclo_id,
            Biometria.estanque_id == estanque_id,
            Biometria.fecha <= fecha,   # <-- antes: < fecha
        )
        .order_by(Biometria.fecha.desc(), Biometria.biometria_id.desc())
        .first()
    )



# ----------------- Servicios públicos -----------------

def list_biometrias(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    estanque_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
    order_by: str = "fecha",
    order: str = "desc",
) -> Tuple[List[Biometria], int]:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)

    q = db.query(Biometria).filter(Biometria.ciclo_id == ciclo_id)

    if estanque_id is not None:
        _ensure_estanque_de_granja_activo(db, estanque_id, granja_id)
        q = q.filter(Biometria.estanque_id == estanque_id)

    if date_from is not None:
        q = q.filter(Biometria.fecha >= date_from)
    if date_to is not None:
        q = q.filter(Biometria.fecha <= date_to)

    valid_order = {
        "fecha": Biometria.fecha,
        "created_at": Biometria.created_at,
    }
    col = valid_order.get(order_by, Biometria.fecha)
    order = (order or "desc").lower()
    q = q.order_by(col.asc() if order == "asc" else col.desc())

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def get_biometria(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    biometria_id: int,
) -> Biometria:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    obj = (
        db.query(Biometria)
        .filter(Biometria.ciclo_id == ciclo_id, Biometria.biometria_id == biometria_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="biometria_not_found")
    return obj


def create_biometria(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    data: Dict,
) -> Biometria:
    """
    Crea una biometría calculando:
      - pp_g = peso_muestra_g / n_muestra
      - incremento_g_sem respecto a la biometría previa del mismo estanque/ciclo (si existe)
      - sob_usada_pct: usa el enviado; si no viene, precarga con SOB vigente
    Si actualiza_sob_operativa=True, registra sob_cambio_log (anterior -> nueva).
    """
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)

    # limpiar campos que no deben llegar o son de contexto
    data.pop("ciclo_id", None)
    data.pop("created_by", None)
    data.pop("pp_g", None)
    data.pop("incremento_g_sem", None)

    est_id = data["estanque_id"]
    _ensure_estanque_de_granja_activo(db, est_id, granja_id)

    # Validación mínima de n_muestra
    n_muestra = int(data["n_muestra"])
    if n_muestra <= 0:
        raise HTTPException(status_code=422, detail="invalid_sample_n: n_muestra debe ser > 0")

    # 1) Calcular pp_g
    peso_g = float(data["peso_muestra_g"])
    pp = peso_g / float(n_muestra)

    # 2) Instancia base
    obj = Biometria(
        ciclo_id=ciclo_id,
        estanque_id=est_id,
        fecha=data["fecha"],
        n_muestra=n_muestra,
        peso_muestra_g=peso_g,
        pp_g=pp,  # <- calculado
        notas=data.get("notas"),
        actualiza_sob_operativa=bool(data.get("actualiza_sob_operativa", True)),
        sob_fuente=data.get("sob_fuente"),
    )
    if hasattr(obj, "created_by"):
        obj.created_by = getattr(user, "usuario_id", None)

    # 3) incremento_g_sem vs biometría previa
    prev = _ultima_biometria_previa(db, ciclo_id=ciclo_id, estanque_id=est_id, fecha=obj.fecha)
    if prev:
        dias = (obj.fecha - prev.fecha).days
        dias = 1 if dias <= 0 else dias  # <-- evita 0
        obj.incremento_g_sem = (float(obj.pp_g) - float(prev.pp_g)) * 7.0 / float(dias)
    else:
        obj.incremento_g_sem = None

    # 4) SOB: precarga vigente si no lo mandan
    sob_vigente = _sob_actual_pct(db, estanque_id=est_id, ciclo_id=ciclo_id)
    sob_entrada = data.get("sob_usada_pct")
    obj.sob_usada_pct = float(sob_entrada) if sob_entrada is not None else sob_vigente

    # Guardar biometría
    db.add(obj)

    # 5) Si piden actualizar SOB operativa, registrar log
    if obj.actualiza_sob_operativa:
        nueva = float(obj.sob_usada_pct)
        fuente = data.get("sob_fuente") or SobFuenteEnum.operativa_actual
        _insert_sob_log(
            db,
            estanque_id=est_id,
            ciclo_id=ciclo_id,
            anterior_pct=float(sob_vigente),
            nueva_pct=nueva,
            actor_id=getattr(user, "usuario_id", None),
            fuente=fuente,
            motivo=obj.notas,
        )

    db.commit()
    db.refresh(obj)
    return obj


def delete_biometria(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    biometria_id: int,
) -> None:
    """
    Eliminación simple. No borra sob_cambio_log (auditoría) aunque exista uno
    creado el mismo día. Si quieres ligarlos, haría falta política adicional.
    """
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    obj = get_biometria(db, user, granja_id, ciclo_id, biometria_id)
    db.delete(obj)
    db.commit()
