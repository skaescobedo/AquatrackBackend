from __future__ import annotations
from datetime import datetime, timezone, date, timedelta
from typing import List, Tuple, Dict, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, asc, desc

from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from models.ciclo import Ciclo
from models.usuario import Usuario

# Planes y entidades para aplicar políticas
from models.estanque import Estanque
from models.siembra_plan import SiembraPlan
from models.siembra_estanque import SiembraEstanque
from models.siembra_fecha_log import SiembraFechaLog
from models.plan_cosechas import PlanCosechas
from models.cosecha_ola import CosechaOla
from models.cosecha_estanque import CosechaEstanque
from models.cosecha_fecha_log import CosechaFechaLog

from services.permissions_service import ensure_user_in_farm_or_admin


# -------- utilidades --------
def _today() -> date:
    return datetime.utcnow().date()


def _evenly_distribute_dates(start: date, end: date, n: int) -> List[date]:
    if n <= 1:
        return [start]
    total_days = (end - start).days
    if total_days < 0:
        total_days = 0
    step = max(0, total_days // (n - 1))
    return [start + timedelta(days=step * i) for i in range(n)]


def list_projections(db: Session, user: Usuario, ciclo_id: int) -> List[Proyeccion]:
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)
    return (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id)
        .order_by(Proyeccion.created_at.desc())
        .all()
    )


def _autopublish_if_first(db: Session, proy: Proyeccion) -> bool:
    has_current = (
        db.query(func.count(Proyeccion.proyeccion_id))
        .filter(Proyeccion.ciclo_id == proy.ciclo_id, Proyeccion.is_current == True)
        .scalar()
        or 0
    )
    if has_current == 0:
        proy.is_current = True
        proy.status = "p"
        proy.published_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(proy)
        return True
    return False


def get_projection_lines(db: Session, user: Usuario, proyeccion_id: int) -> List[ProyeccionLinea]:
    p = db.get(Proyeccion, proyeccion_id)
    if not p:
        raise HTTPException(status_code=404, detail="projection_not_found")
    ciclo = db.get(Ciclo, p.ciclo_id)
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)
    return (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx), asc(ProyeccionLinea.fecha_plan))
        .all()
    )


# -------- helpers publish / estado de siembras --------
def _is_seeding_locked(db: Session, ciclo_id: int) -> bool:
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        return False
    total = db.query(func.count(SiembraEstanque.siembra_estanque_id)).filter(SiembraEstanque.siembra_plan_id == plan.siembra_plan_id).scalar() or 0
    if total == 0:
        return False
    finalizadas = db.query(func.count(SiembraEstanque.siembra_estanque_id)).filter(
        SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
        SiembraEstanque.estado == "f"
    ).scalar() or 0
    return finalizadas == total


def _last_seeding_date(db: Session, ciclo_id: int) -> Optional[date]:
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        return None
    last_date = (
        db.query(func.max(SiembraEstanque.fecha_siembra))
        .filter(
            SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
            SiembraEstanque.estado == "f",
            SiembraEstanque.fecha_siembra.isnot(None),
        )
        .scalar()
    )
    return last_date


def _derive_harvest_window(db: Session, proyeccion_id: int) -> tuple[date, date]:
    q = (
        db.query(ProyeccionLinea.fecha_plan)
        .filter(
            ProyeccionLinea.proyeccion_id == proyeccion_id,
            ((ProyeccionLinea.cosecha_flag == True) | ((ProyeccionLinea.retiro_org_m2.isnot(None)) & (ProyeccionLinea.retiro_org_m2 > 0)))
        )
        .order_by(asc(ProyeccionLinea.fecha_plan))
    )
    fechas = [r[0] for r in q.all()]
    if fechas:
        return fechas[0], fechas[-1]
    last = (
        db.query(ProyeccionLinea.fecha_plan)
        .filter(ProyeccionLinea.proyeccion_id == proyeccion_id)
        .order_by(asc(ProyeccionLinea.fecha_plan))
        .all()
    )
    if not last:
        t = _today()
        return t, t
    return last[-1][0], last[-1][0]


def _get_or_create_final_wave(db: Session, user: Usuario, ciclo: Ciclo) -> CosechaOla:
    plan = db.query(PlanCosechas).filter(PlanCosechas.ciclo_id == ciclo.ciclo_id).first()
    if not plan:
        plan = PlanCosechas(ciclo_id=ciclo.ciclo_id, nota_operativa="Auto", created_by=user.usuario_id)
        db.add(plan)
        db.flush()
    ola = (
        db.query(CosechaOla)
        .filter(CosechaOla.plan_cosechas_id == plan.plan_cosechas_id, CosechaOla.tipo == "f")
        .order_by(asc(CosechaOla.orden), asc(CosechaOla.ventana_inicio))
        .first()
    )
    if not ola:
        ola = CosechaOla(
            plan_cosechas_id=plan.plan_cosechas_id,
            nombre="Ola Final",
            tipo="f",
            ventana_inicio=_today(),
            ventana_fin=_today(),
            estado="p",
            orden=1,
            created_by=user.usuario_id,
        )
        db.add(ola)
        db.flush()
    return ola


# -------- aplicar políticas (hoy no usadas al publicar) --------
def _apply_seeding_sync(db: Session, user: Usuario, ciclo: Ciclo, proy: Proyeccion) -> Dict[str, int]:
    stats = {"updated": 0, "deleted": 0, "created": 0}
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo.ciclo_id).first()
    if not plan:
        return stats

    if proy.siembra_ventana_fin:
        plan.ventana_fin = proy.siembra_ventana_fin

    q = (
        db.query(SiembraEstanque)
        .filter(SiembraEstanque.siembra_plan_id == plan.siembra_plan_id, SiembraEstanque.estado == "p")
        .order_by(asc(SiembraEstanque.estanque_id))
    )
    items = q.all()
    if not items:
        db.commit()
        return stats

    fechas = _evenly_distribute_dates(plan.ventana_inicio, plan.ventana_fin, len(items))
    for se, new_date in zip(items, fechas):
        if se.fecha_tentativa != new_date:
            log = SiembraFechaLog(
                siembra_estanque_id=se.siembra_estanque_id,
                fecha_anterior=se.fecha_tentativa,
                fecha_nueva=new_date,
                motivo="publish_sync",
                changed_by=user.usuario_id,
            )
            db.add(log)
            se.fecha_tentativa = new_date
            stats["updated"] += 1

    db.commit()
    return stats


def _apply_seeding_regen(db: Session, user: Usuario, ciclo: Ciclo, proy: Proyeccion) -> Dict[str, int]:
    stats = {"updated": 0, "deleted": 0, "created": 0}
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo.ciclo_id).first()
    if not plan:
        return stats

    if proy.siembra_ventana_fin:
        plan.ventana_fin = proy.siembra_ventana_fin

    deleted = (
        db.query(SiembraEstanque)
        .filter(SiembraEstanque.siembra_plan_id == plan.siembra_plan_id, SiembraEstanque.estado == "p")
        .delete(synchronize_session=False)
    )
    stats["deleted"] = int(deleted or 0)
    db.flush()

    existing_estanques = {e[0] for e in db.query(SiembraEstanque.estanque_id).filter(SiembraEstanque.siembra_plan_id == plan.siembra_plan_id).all()}
    all_ponds = (
        db.query(Estanque)
        .filter(Estanque.granja_id == ciclo.granja_id)
        .order_by(asc(Estanque.estanque_id))
        .all()
    )
    candidates = [p for p in all_ponds if p.estanque_id not in existing_estanques]
    if candidates:
        fechas = _evenly_distribute_dates(plan.ventana_inicio, plan.ventana_fin, len(candidates))
        bulk = []
        for p, d in zip(candidates, fechas):
            bulk.append(
                SiembraEstanque(
                    siembra_plan_id=plan.siembra_plan_id,
                    estanque_id=p.estanque_id,
                    estado="p",
                    fecha_tentativa=d,
                    created_by=user.usuario_id,
                )
            )
        db.bulk_save_objects(bulk)
        stats["created"] = len(bulk)

    db.commit()
    return stats


def _apply_harvest_sync(db: Session, user: Usuario, ciclo: Ciclo, proy: Proyeccion) -> Dict[str, int]:
    stats = {"updated": 0, "deleted": 0, "created": 0}
    ola = _get_or_create_final_wave(db, user, ciclo)
    v_ini, v_fin = _derive_harvest_window(db, proy.proyeccion_id)
    ola.ventana_inicio, ola.ventana_fin = v_ini, v_fin

    today = _today()
    q = (
        db.query(CosechaEstanque)
        .filter(
            CosechaEstanque.cosecha_ola_id == ola.cosecha_ola_id,
            CosechaEstanque.estado == "p",
            CosechaEstanque.fecha_cosecha >= today,
        )
        .order_by(asc(CosechaEstanque.estanque_id))
    )
    items = q.all()
    if not items:
        db.commit()
        return stats

    fechas = _evenly_distribute_dates(ola.ventana_inicio, ola.ventana_fin, len(items))
    for ce, new_date in zip(items, fechas):
        if ce.fecha_cosecha != new_date:
            log = CosechaFechaLog(
                cosecha_estanque_id=ce.cosecha_estanque_id,
                fecha_anterior=ce.fecha_cosecha,
                fecha_nueva=new_date,
                motivo="publish_sync",
                changed_by=user.usuario_id,
            )
            db.add(log)
            ce.fecha_cosecha = new_date
            stats["updated"] += 1

    db.commit()
    return stats


def _apply_harvest_regen(db: Session, user: Usuario, ciclo: Ciclo, proy: Proyeccion) -> Dict[str, int]:
    stats = {"updated": 0, "deleted": 0, "created": 0}
    ola = _get_or_create_final_wave(db, user, ciclo)
    v_ini, v_fin = _derive_harvest_window(db, proy.proyeccion_id)
    ola.ventana_inicio, ola.ventana_fin = v_ini, v_fin

    today = _today()

    deleted = (
        db.query(CosechaEstanque)
        .filter(
            CosechaEstanque.cosecha_ola_id == ola.cosecha_ola_id,
            CosechaEstanque.estado == "p",
            CosechaEstanque.fecha_cosecha >= today,
        )
        .delete(synchronize_session=False)
    )
    stats["deleted"] = int(deleted or 0)
    db.flush()

    ponds = (
        db.query(Estanque)
        .filter(Estanque.granja_id == ciclo.granja_id)
        .order_by(asc(Estanque.estanque_id))
        .all()
    )
    estanques_con_c = {r[0] for r in db.query(CosechaEstanque.estanque_id).filter(
        CosechaEstanque.cosecha_ola_id == ola.cosecha_ola_id,
        CosechaEstanque.estado == "c"
    ).all()}

    candidates = [p for p in ponds if p.estanque_id not in estanques_con_c]
    if candidates:
        fechas = _evenly_distribute_dates(ola.ventana_inicio, ola.ventana_fin, len(candidates))
        bulk = []
        for p, d in zip(candidates, fechas):
            bulk.append(
                CosechaEstanque(
                    estanque_id=p.estanque_id,
                    cosecha_ola_id=ola.cosecha_ola_id,
                    estado="p",
                    fecha_cosecha=d,
                    created_by=user.usuario_id,
                )
            )
        db.bulk_save_objects(bulk)
        stats["created"] = len(bulk)

    db.commit()
    return stats


# -------- helpers Reforecast --------
# -------- helpers para published/current (compatibles con MySQL) --------
def _current_published_projection(db: Session, ciclo_id: int) -> Optional[Proyeccion]:
    """
    Proyección 'publicada' preferida:
    - Primero la vigente (is_current DESC)
    - Luego cualquier publicada (published_at no nulo) más reciente.
    Nota: orden MySQL-friendly para NULLS LAST en published_at.
    """
    return (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id)
        .order_by(
            Proyeccion.is_current.desc(),
            Proyeccion.published_at.is_(None).asc(),  # NULLS LAST
            Proyeccion.published_at.desc(),
            Proyeccion.created_at.desc(),
        )
        .first()
    )


def _first_line_date(db: Session, proyeccion_id: int) -> Optional[date]:
    first = (
        db.query(ProyeccionLinea.fecha_plan)
        .filter(ProyeccionLinea.proyeccion_id == proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx), asc(ProyeccionLinea.fecha_plan))
        .first()
    )
    return first[0] if first else None


def _next_sunday_on_or_after(d: date) -> date:
    # Monday=0 ... Sunday=6
    delta = (6 - d.weekday()) % 7
    return d + timedelta(days=delta)


def create_initial_reforecast_if_ready(db: Session, user: Usuario, ciclo_id: int) -> Optional[Proyeccion]:
    if not _is_seeding_locked(db, ciclo_id):
        return None

    existing_draft = (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id, Proyeccion.status == "b")
        .first()
    )
    if existing_draft:
        return None

    src = _current_published_projection(db, ciclo_id)
    if not src:
        src = (
            db.query(Proyeccion)
            .filter(Proyeccion.ciclo_id == ciclo_id)
            .order_by(desc(Proyeccion.created_at))
            .first()
        )
        if not src:
            return None

    return reforecast(db, user, src.proyeccion_id, "Reforecast inicial tras cierre de siembras")


def reforecast(db: Session, user: Usuario, proyeccion_id: int, descripcion: str | None) -> Proyeccion:
    src = db.get(Proyeccion, proyeccion_id)
    if not src:
        raise HTTPException(status_code=404, detail="projection_not_found")
    ciclo = db.get(Ciclo, src.ciclo_id)
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    # Gate — requiere todas las siembras confirmadas
    if not _is_seeding_locked(db, src.ciclo_id):
        raise HTTPException(status_code=409, detail="reforecast_requires_all_seedings_confirmed")

    existing_draft = (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == src.ciclo_id, Proyeccion.status == "b")
        .first()
    )
    if existing_draft:
        raise HTTPException(status_code=409, detail="draft_projection_already_exists")

    count_versions = db.query(func.count(Proyeccion.proyeccion_id)).filter(Proyeccion.ciclo_id == src.ciclo_id).scalar() or 0
    new_version = f"v{count_versions + 1}"

    draft = Proyeccion(
        ciclo_id=src.ciclo_id,
        version=new_version,
        descripcion=descripcion or f"Borrador reforecast de {src.version}",
        status="b",
        is_current=False,
        creada_por=user.usuario_id,
        source_type="reforecast",
        parent_version_id=src.proyeccion_id,
        sob_final_objetivo_pct=src.sob_final_objetivo_pct,
        siembra_ventana_fin=src.siembra_ventana_fin,  # puede actualizarse abajo
    )
    db.add(draft)
    db.flush()

    # --- Rebase por última siembra confirmada (solo si difiere ≥ 7 días) ---
    orig_start = _first_line_date(db, src.proyeccion_id)
    real_start = _last_seeding_date(db, src.ciclo_id)
    shift_dates = False
    if orig_start and real_start:
        if (real_start - orig_start).days >= 7:
            shift_dates = True

    # Traemos líneas de la fuente para clonar
    src_lines = (
        db.query(ProyeccionLinea)
        .filter(ProyeccionLinea.proyeccion_id == src.proyeccion_id)
        .order_by(asc(ProyeccionLinea.semana_idx), asc(ProyeccionLinea.fecha_plan))
        .all()
    )

    # Preparar base de domingos si vamos a reajustar
    is_first_sunday = bool(real_start and real_start.weekday() == 6)
    base_sunday = None
    if shift_dates and real_start:
        base_sunday = real_start if is_first_sunday else _next_sunday_on_or_after(real_start)

    clones = []
    for i, l in enumerate(src_lines):
        if shift_dates and real_start:
            if i == 0:
                new_date = real_start  # puede no ser domingo
            else:
                steps = i if is_first_sunday else (i - 1)
                new_date = base_sunday + timedelta(days=7 * steps)
            edad_dias = i * 7
        else:
            new_date = l.fecha_plan
            edad_dias = l.edad_dias

        clones.append(
            ProyeccionLinea(
                proyeccion_id=draft.proyeccion_id,
                edad_dias=edad_dias,
                semana_idx=l.semana_idx,       # preservamos índices
                fecha_plan=new_date,           # posiblemente reajustada
                pp_g=l.pp_g,
                incremento_g_sem=l.incremento_g_sem,
                sob_pct_linea=l.sob_pct_linea,
                cosecha_flag=l.cosecha_flag,
                retiro_org_m2=l.retiro_org_m2,
                nota=l.nota,
            )
        )

    if clones:
        db.bulk_save_objects(clones)

    # Si se rebasó, actualizamos el top-level para reflejar el nuevo inicio
    if shift_dates and real_start:
        draft.siembra_ventana_fin = real_start

    db.commit()
    db.refresh(draft)
    return draft


# -------- Publicar (solo inmortaliza) --------
def publish(db: Session, user: Usuario, proyeccion_id: int):
    p = db.get(Proyeccion, proyeccion_id)
    if not p:
        raise HTTPException(status_code=404, detail="projection_not_found")

    ciclo = db.get(Ciclo, p.ciclo_id)
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    current = (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == p.ciclo_id, Proyeccion.is_current == True)
        .all()
    )
    for c in current:
        if c.proyeccion_id != p.proyeccion_id:
            c.is_current = False

    p.is_current = True
    p.status = "p"
    p.published_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(p)

    return {
        "applied": False,
        "impact_summary": "published_only_no_sync",
        "proyeccion_id": p.proyeccion_id,
        "seeding_locked": False,
        "seeding_stats": {"updated": 0, "deleted": 0, "created": 0},
        "harvest_stats": {"updated": 0, "deleted": 0, "created": 0},
    }
