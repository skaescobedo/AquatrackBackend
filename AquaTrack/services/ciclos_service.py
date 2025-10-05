from typing import Dict, List, Optional, Tuple
from datetime import date
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.usuario import Usuario
from models.granja import Granja
from models.ciclo import Ciclo

# Dependencias que podrían existir (se usan en guards; son opcionales)
# Intenta importarlas si están disponibles para evitar romper el flujo
try:
    from models.siembra_plan import SiembraPlan
except Exception:
    SiembraPlan = None

try:
    from models.siembra_estanque import SiembraEstanque
except Exception:
    SiembraEstanque = None

try:
    from models.biometria import Biometria
except Exception:
    Biometria = None

try:
    from models.cosecha_ola import CosechaOla
except Exception:
    CosechaOla = None

try:
    from models.cosecha_estanque import CosechaEstanque
except Exception:
    CosechaEstanque = None

try:
    from models.proyeccion import Proyeccion
except Exception:
    Proyeccion = None

from enums.enums import CicloEstadoEnum
from enums.roles import Role
from utils.permissions import user_has_any_role, is_user_associated_to_granja
from utils.permissions import ensure_visibility_granja  # misma política not-found


# ---------------------------
# Selectores y visibilidad
# ---------------------------

def _ensure_granja_visible(db: Session, user: Usuario, granja_id: int) -> None:
    if not user_has_any_role(user, [Role.admin_global]):
        if not is_user_associated_to_granja(db, user.usuario_id, granja_id):
            raise HTTPException(status_code=404, detail="granja_not_found: No existe o no tienes acceso.")

def _query_visible_ciclos(db: Session, user: Usuario, granja_id: int):
    _ensure_granja_visible(db, user, granja_id)
    return db.query(Ciclo).filter(Ciclo.granja_id == granja_id)

def list_ciclos(
    db: Session,
    user: Usuario,
    granja_id: int,
    q: Optional[str],
    estado: Optional[CicloEstadoEnum],
    page: int,
    page_size: int,
    order_by: str,
    order: str,
) -> Tuple[List[Ciclo], int]:
    query = _query_visible_ciclos(db, user, granja_id)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(Ciclo.nombre.ilike(like))

    if estado:
        query = query.filter(Ciclo.estado == estado)

    valid_order = {"nombre": Ciclo.nombre, "fecha_inicio": Ciclo.fecha_inicio, "created_at": Ciclo.created_at}
    col = valid_order.get(order_by, Ciclo.created_at)
    query = query.order_by(col.asc() if order == "asc" else col.desc())

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total

def get_ciclo_visible(db: Session, user: Usuario, granja_id: int, ciclo_id: int) -> Ciclo:
    _ensure_granja_visible(db, user, granja_id)
    obj = db.query(Ciclo).filter(Ciclo.granja_id == granja_id, Ciclo.ciclo_id == ciclo_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="ciclo_not_found: No existe o no tienes acceso.")
    return obj

def get_ciclo_activo(db: Session, user: Usuario, granja_id: int) -> Optional[Ciclo]:
    _ensure_granja_visible(db, user, granja_id)
    return (
        db.query(Ciclo)
          .filter(Ciclo.granja_id == granja_id, Ciclo.estado == CicloEstadoEnum.a)
          .order_by(Ciclo.fecha_inicio.desc())
          .first()
    )


# ---------------------------
# Reglas de dominio (guards)
# ---------------------------

def _validar_fechas_creacion(fecha_inicio: date, fecha_fin_planificada: Optional[date]) -> None:
    if fecha_fin_planificada and fecha_fin_planificada < fecha_inicio:
        raise HTTPException(status_code=422, detail="date_range_invalid: fecha_fin_planificada < fecha_inicio.")

def _validar_unico_activo(db: Session, granja_id: int) -> None:
    existe_activo = db.query(Ciclo).filter(
        Ciclo.granja_id == granja_id,
        Ciclo.estado == CicloEstadoEnum.a
    ).first() is not None
    if existe_activo:
        raise HTTPException(status_code=409, detail="active_cycle_exists: Ya existe un ciclo activo en esta granja.")

def _validar_cierre_fechas(ciclo: Ciclo, fecha_cierre_real: Optional[date]) -> date:
    cierre = fecha_cierre_real or date.today()
    if cierre < ciclo.fecha_inicio:
        raise HTTPException(status_code=422, detail="close_date_invalid: fecha_cierre_real < fecha_inicio del ciclo.")
    return cierre

def _ciclo_tiene_dependencias(db: Session, ciclo_id: int) -> bool:
    # Si existen tablas, valida referencias mínimas para eliminar
    def exists(q):
        try:
            return db.query(q.exists()).scalar()
        except Exception:
            return False

    has_plan = exists(db.query(SiembraPlan.ciclo_id).filter(SiembraPlan.ciclo_id == ciclo_id)) if SiembraPlan else False
    has_siembras = exists(db.query(SiembraEstanque.ciclo_id).filter(SiembraEstanque.ciclo_id == ciclo_id)) if SiembraEstanque else False
    has_bios = exists(db.query(Biometria.ciclo_id).filter(Biometria.ciclo_id == ciclo_id)) if Biometria else False
    has_olas = exists(db.query(CosechaOla.ciclo_id).filter(CosechaOla.ciclo_id == ciclo_id)) if CosechaOla else False
    has_cosechas = exists(db.query(CosechaEstanque.ciclo_id).filter(CosechaEstanque.ciclo_id == ciclo_id)) if CosechaEstanque else False
    has_proy = exists(db.query(Proyeccion.ciclo_id).filter(Proyeccion.ciclo_id == ciclo_id)) if Proyeccion else False

    return any([has_plan, has_siembras, has_bios, has_olas, has_cosechas, has_proy])


# ---------------------------
# Mutaciones
# ---------------------------

def create_ciclo(db: Session, user: Usuario, granja_id: int, data: Dict) -> Ciclo:
    # Seguridad de ámbito
    _ensure_granja_visible(db, user, granja_id)

    # La granja debe existir
    if db.query(Granja).filter(Granja.granja_id == granja_id).first() is None:
        raise HTTPException(status_code=404, detail="granja_not_found: No existe o no tienes acceso.")

    # Si el payload trae granja_id y no coincide → conflicto (tolerancia defensiva)
    body_gid = data.get("granja_id")
    if body_gid is not None and body_gid != granja_id:
        raise HTTPException(status_code=409, detail="granja_id_mismatch: El ID de la granja del body no coincide con la URL.")

    # Validaciones de fechas
    _validar_fechas_creacion(
        fecha_inicio=data["fecha_inicio"],
        fecha_fin_planificada=data.get("fecha_fin_planificada")
    )

    # Regla: un único ciclo activo por granja
    # (si el estado de creación es 'a', valida)
    estado = data.get("estado")
    if (estado is None) or (estado == CicloEstadoEnum.a):
        _validar_unico_activo(db, granja_id)

    # Inyecta granja_id desde el path SIEMPRE
    obj = Ciclo(**data, granja_id=granja_id)

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def update_ciclo(db: Session, user: Usuario, granja_id: int, ciclo_id: int, changes: Dict) -> Ciclo:
    obj = get_ciclo_visible(db, user, granja_id, ciclo_id)

    # Si se intenta pasar de 'a' → 't', validar
    if "estado" in changes and changes["estado"] == CicloEstadoEnum.t:
        cierre = _validar_cierre_fechas(obj, changes.get("fecha_cierre_real"))
        changes.setdefault("fecha_cierre_real", cierre)

    # Si se intenta activar un ciclo (poco común en update), validar único activo
    if "estado" in changes and changes["estado"] == CicloEstadoEnum.a:
        # Evita que haya dos activos (excluyendo el mismo ciclo)
        existe_otro_activo = db.query(Ciclo).filter(
            Ciclo.granja_id == granja_id,
            Ciclo.estado == CicloEstadoEnum.a,
            Ciclo.ciclo_id != ciclo_id
        ).first() is not None
        if existe_otro_activo:
            raise HTTPException(status_code=409, detail="active_cycle_exists: Ya existe otro ciclo activo en esta granja.")

    # Validaciones de fechas si cambian
    if "fecha_inicio" in changes or "fecha_fin_planificada" in changes:
        _validar_fechas_creacion(
            fecha_inicio=changes.get("fecha_inicio", obj.fecha_inicio),
            fecha_fin_planificada=changes.get("fecha_fin_planificada", obj.fecha_fin_planificada)
        )

    # Aplicar cambios
    for k, v in changes.items():
        setattr(obj, k, v)

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def close_ciclo(db: Session, user: Usuario, granja_id: int, ciclo_id: int, fecha_cierre_real: Optional[date]) -> Ciclo:
    obj = get_ciclo_visible(db, user, granja_id, ciclo_id)
    if obj.estado == CicloEstadoEnum.t:
        return obj  # idempotente

    cierre = _validar_cierre_fechas(obj, fecha_cierre_real)
    obj.estado = CicloEstadoEnum.t
    obj.fecha_cierre_real = cierre

    db.add(obj)
    db.commit()
    db.refresh(obj)

    # (Opcional) Aquí podrías disparar el resumen automático del ciclo:
    # cycles_summary_service.generate_for_ciclo(db, obj.ciclo_id)
    return obj

def delete_ciclo(db: Session, user: Usuario, granja_id: int, ciclo_id: int) -> None:
    obj = get_ciclo_visible(db, user, granja_id, ciclo_id)

    # Política: solo eliminar si está TERMINADO y sin dependencias vivas
    if obj.estado != CicloEstadoEnum.t:
        raise HTTPException(status_code=409, detail="cycle_not_terminated: Solo puedes eliminar ciclos terminados.")
    if _ciclo_tiene_dependencias(db, ciclo_id):
        raise HTTPException(status_code=409, detail="cycle_in_use: El ciclo tiene dependencias y no puede eliminarse.")

    db.delete(obj)
    db.commit()

def get_ciclo_activo_or_404(db: Session, user: Usuario, granja_id: int) -> Ciclo:
    # Visibilidad
    if not user_has_any_role(user, [Role.admin_global]):
        if not is_user_associated_to_granja(db, user.usuario_id, granja_id):
            raise HTTPException(status_code=404, detail="granja_not_found: No existe o no tienes acceso.")
    # Ciclo activo (debe ser único por regla)
    obj = (
        db.query(Ciclo)
          .filter(Ciclo.granja_id == granja_id, Ciclo.estado == CicloEstadoEnum.a)
          .order_by(Ciclo.fecha_inicio.desc())
          .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="active_cycle_not_found: La granja no tiene ciclo activo.")
    return obj