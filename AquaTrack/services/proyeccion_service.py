# services/proyeccion_service.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.usuario import Usuario
from models.ciclo import Ciclo
from models.siembra_plan import SiembraPlan
from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from enums.roles import Role
from enums.enums import CicloEstadoEnum, ProyeccionStatusEnum, ProyeccionSourceEnum
from utils.permissions import user_has_any_role, is_user_associated_to_granja


# --------- Helpers de alcance/validación ---------

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


def _ensure_plan_or_409(db: Session, ciclo_id: int) -> SiembraPlan:
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        raise HTTPException(status_code=409, detail="seeding_plan_missing: El ciclo no tiene plan de siembras.")
    return plan


def _version_auto(db: Session, ciclo_id: int) -> str:
    # v{N+1} según cantidad actual
    cnt = db.query(func.count(Proyeccion.proyeccion_id))\
            .filter(Proyeccion.ciclo_id == ciclo_id).scalar() or 0
    return f"v{cnt + 1}"


def _validar_version_unica(db: Session, ciclo_id: int, version: str) -> None:
    exists = (
        db.query(Proyeccion.proyeccion_id)
          .filter(Proyeccion.ciclo_id == ciclo_id, Proyeccion.version == version)
          .first()
        is not None
    )
    if exists:
        raise HTTPException(status_code=409, detail="projection_version_exists")


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _daterange_weeks(start: date, end: date) -> List[date]:
    # inclusivo por inicio; genera fechas cada 7 días hasta <= end
    days = (end - start).days
    if days < 0:
        return []
    n_weeks = (days // 7) + 1
    return [start + timedelta(days=7 * i) for i in range(n_weeks)]


# --------- Listar / Obtener proyecciones ---------

def list_proyecciones(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    page: int,
    page_size: int,
    order_by: str,
    order: str,
    status: Optional[ProyeccionStatusEnum],
) -> Tuple[List[Proyeccion], int]:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)

    q = db.query(Proyeccion).filter(Proyeccion.ciclo_id == ciclo_id)
    if status:
        q = q.filter(Proyeccion.status == status)

    valid_order = {
        "created_at": Proyeccion.created_at,
        "updated_at": Proyeccion.updated_at,
        "version": Proyeccion.version,
        "is_current": Proyeccion.is_current,
        "published_at": Proyeccion.published_at,
    }
    col = valid_order.get(order_by, Proyeccion.created_at)
    q = q.order_by(col.asc() if order == "asc" else col.desc())

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def get_proyeccion(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    proyeccion_id: int
) -> Proyeccion:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)

    obj = db.query(Proyeccion).filter(
        Proyeccion.ciclo_id == ciclo_id,
        Proyeccion.proyeccion_id == proyeccion_id
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="projection_not_found")
    return obj


# --------- Factories (solo creación por factories) ---------

def bootstrap_from_plan(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    *,
    version: Optional[str] = None,
    descripcion: Optional[str] = None,
    sob_final_objetivo_pct: Optional[float] = None,
    incremento_semanal_g: Optional[float] = 1.0,   # heurística simple por ahora
    sob_base_pct: Optional[float] = 90.0,          # base para línea; se interpola a objetivo si viene
) -> Proyeccion:
    ciclo = _ensure_scope(db, user, granja_id, ciclo_id)
    _validar_ciclo_activo(ciclo)
    plan = _ensure_plan_or_409(db, ciclo_id)

    ver = version or _version_auto(db, ciclo_id)
    _validar_version_unica(db, ciclo_id, ver)

    proy = Proyeccion(
        ciclo_id=ciclo_id,
        version=ver,
        descripcion=descripcion or "Bootstrap desde plan de siembras",
        status=ProyeccionStatusEnum.b,      # borrador
        is_current=False,
        source_type=ProyeccionSourceEnum.auto,
        sob_final_objetivo_pct=sob_final_objetivo_pct,
        siembra_ventana_inicio=plan.ventana_inicio,
        creada_por=getattr(user, "usuario_id", None),
    )

    db.add(proy)
    db.commit()
    db.refresh(proy)

    # Construir timeline semanal
    start = plan.ventana_inicio
    end = ciclo.fecha_fin_planificada or plan.ventana_fin
    fechas = _daterange_weeks(start, end)
    if not fechas:
        # Si no hay rango, crear al menos una línea con la fecha de inicio
        fechas = [start]

    # Heurística pp_g: arranca en talla_inicial_g y suma incremento_semanal_g por semana
    pp = float(plan.talla_inicial_g)
    inc = float(incremento_semanal_g or 0.0)

    # Heurística SOB: arranca en sob_base_pct y, si hay sob_final_objetivo_pct, interpola linealmente
    base_sob = _clamp(float(sob_base_pct or 90.0), 0.0, 100.0)
    tgt_sob = sob_final_objetivo_pct
    n = max(1, len(fechas))  # evitar división entre 0

    lineas: List[ProyeccionLinea] = []
    for idx, f in enumerate(fechas):
        # Interpolación SOB (si hay target)
        if tgt_sob is not None:
            # idx=0 → base_sob, idx=n-1 → tgt_sob
            t = idx / (n - 1) if n > 1 else 1.0
            sob_val = _clamp(base_sob + (float(tgt_sob) - base_sob) * t, 0.0, 100.0)
        else:
            sob_val = base_sob

        linea = ProyeccionLinea(
            proyeccion_id=proy.proyeccion_id,
            edad_dias=idx * 7,
            semana_idx=idx,
            fecha_plan=f,
            pp_g=pp,
            sob_pct_linea=sob_val,
            incremento_g_sem=(None if idx == 0 else inc),
            cosecha_flag=False,
            retiro_org_m2=None,
            nota=None,
        )
        lineas.append(linea)
        pp = pp + inc  # avanzar pp para la siguiente semana

    db.add_all(lineas)
    db.commit()
    db.refresh(proy)
    return proy


def bootstrap_from_archivo(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    *,
    archivo_id: int,
    version: Optional[str] = None,
    descripcion: Optional[str] = None,
) -> Proyeccion:
    # Dejar explícito que falta hasta integrar "archivo"
    raise HTTPException(status_code=501, detail="projection_from_file_not_implemented")


# --------- Publicar / set current ---------

def publish_proyeccion(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    proyeccion_id: int,
    *,
    set_current: bool = True,
) -> Proyeccion:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    proy = get_proyeccion(db, user, granja_id, ciclo_id, proyeccion_id)

    proy.status = ProyeccionStatusEnum.p  # publicada
    proy.published_at = datetime.utcnow()
    if set_current:
        # remover current de las demás del ciclo
        db.query(Proyeccion)\
          .filter(Proyeccion.ciclo_id == ciclo_id, Proyeccion.proyeccion_id != proy.proyeccion_id)\
          .update({Proyeccion.is_current: False})
        proy.is_current = True

    db.add(proy)
    db.commit()
    db.refresh(proy)
    return proy


def set_current(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    proyeccion_id: int,
) -> Proyeccion:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    proy = get_proyeccion(db, user, granja_id, ciclo_id, proyeccion_id)

    db.query(Proyeccion)\
      .filter(Proyeccion.ciclo_id == ciclo_id, Proyeccion.proyeccion_id != proy.proyeccion_id)\
      .update({Proyeccion.is_current: False})
    proy.is_current = True
    db.add(proy)
    db.commit()
    db.refresh(proy)
    return proy


# --------- Líneas: listar / reemplazar ---------

def list_lineas(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    proyeccion_id: int,
    order_by: str,
    order: str,
) -> List[ProyeccionLinea]:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    _ = get_proyeccion(db, user, granja_id, ciclo_id, proyeccion_id)

    q = db.query(ProyeccionLinea).filter(ProyeccionLinea.proyeccion_id == proyeccion_id)

    valid_order = {
        "semana_idx": ProyeccionLinea.semana_idx,
        "fecha_plan": ProyeccionLinea.fecha_plan,
        "pp_g": ProyeccionLinea.pp_g,
    }
    col = valid_order.get(order_by, ProyeccionLinea.semana_idx)
    q = q.order_by(col.asc() if order == "asc" else col.desc())

    return q.all()


def replace_lineas(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    proyeccion_id: int,
    items: List[Dict],
) -> Proyeccion:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    proy = get_proyeccion(db, user, granja_id, ciclo_id, proyeccion_id)

    # Borrar existentes
    db.query(ProyeccionLinea).filter(ProyeccionLinea.proyeccion_id == proy.proyeccion_id).delete()

    # Insertar nuevas (se asume payload válido; cualquier validación dura la puedes añadir aquí)
    nuevas: List[ProyeccionLinea] = []
    for it in items:
        linea = ProyeccionLinea(
            proyeccion_id=proy.proyeccion_id,
            edad_dias=int(it.get("edad_dias", 0)),
            semana_idx=int(it.get("semana_idx", 0)),
            fecha_plan=it["fecha_plan"],
            pp_g=float(it["pp_g"]),
            sob_pct_linea=float(it.get("sob_pct_linea", 90.0)),
            incremento_g_sem=it.get("incremento_g_sem"),
            cosecha_flag=bool(it.get("cosecha_flag", False)),
            retiro_org_m2=it.get("retiro_org_m2"),
            nota=it.get("nota"),
        )
        nuevas.append(linea)

    if nuevas:
        db.add_all(nuevas)
    db.commit()
    db.refresh(proy)
    return proy


# --------- Borrar proyección (opcional) ---------

def delete_proyeccion(
    db: Session,
    user: Usuario,
    granja_id: int,
    ciclo_id: int,
    proyeccion_id: int,
) -> None:
    _ = _ensure_scope(db, user, granja_id, ciclo_id)
    proy = get_proyeccion(db, user, granja_id, ciclo_id, proyeccion_id)

    # Por prudencia: no borrar publicadas ni current
    if proy.status == ProyeccionStatusEnum.p or proy.is_current:
        raise HTTPException(status_code=409, detail="projection_locked: No puedes borrar una proyección publicada o current.")

    db.delete(proy)
    db.commit()
