# services/proyeccion_adapter.py
from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from config.settings import settings
from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from enums.enums import ProyeccionStatusEnum

def hay_publicada(db: Session, ciclo_id: int) -> bool:
    return db.query(Proyeccion.proyeccion_id)\
             .filter(Proyeccion.ciclo_id == ciclo_id, Proyeccion.status == ProyeccionStatusEnum.p)\
             .first() is not None

def _find_borrador(db: Session, ciclo_id: int) -> Optional[Proyeccion]:
    return db.query(Proyeccion).filter(
        Proyeccion.ciclo_id == ciclo_id, Proyeccion.status == ProyeccionStatusEnum.b
    ).order_by(Proyeccion.updated_at.desc()).first()

def _find_current_published(db: Session, ciclo_id: int) -> Optional[Proyeccion]:
    return db.query(Proyeccion).filter(
        Proyeccion.ciclo_id == ciclo_id, Proyeccion.status == ProyeccionStatusEnum.p, Proyeccion.is_current == True
    ).first()

def _clone_header(db: Session, src: Proyeccion) -> Proyeccion:
    return Proyeccion(
        ciclo_id=src.ciclo_id,
        version=f"{src.version}-b",
        descripcion=f"Draft de {src.version}",
        status=ProyeccionStatusEnum.b,
        is_current=False,
        published_at=None,
        creada_por=src.creada_por,
        source_type=src.source_type,
        source_ref=src.source_ref,
        parent_version_id=src.proyeccion_id,
        sob_final_objetivo_pct=src.sob_final_objetivo_pct,
        siembra_ventana_inicio=src.siembra_ventana_inicio,
    )

def get_or_create_borrador(db: Session, ciclo_id: int) -> Optional[int]:
    if not getattr(settings, "PROYECCION_HOOKS_ENABLED", True):
        return None
    # Si hay borrador, úsalo
    draft = _find_borrador(db, ciclo_id)
    if draft:
        return draft.proyeccion_id

    # ¿Clonar desde la publicada actual?
    if getattr(settings, "PROYECCION_CLONE_FROM_CURRENT_ON_MUTATIONS", True):
        current = _find_current_published(db, ciclo_id)
        if current:
            new = _clone_header(db, current)
            db.add(new); db.commit(); db.refresh(new)
            # clonar líneas
            src_lines = db.query(ProyeccionLinea).filter(ProyeccionLinea.proyeccion_id == current.proyeccion_id).all()
            if src_lines:
                clones = [ProyeccionLinea(
                    proyeccion_id=new.proyeccion_id,
                    edad_dias=l.edad_dias, semana_idx=l.semana_idx, fecha_plan=l.fecha_plan,
                    pp_g=l.pp_g, sob_pct_linea=l.sob_pct_linea, incremento_g_sem=l.incremento_g_sem,
                    cosecha_flag=l.cosecha_flag, retiro_org_m2=l.retiro_org_m2, nota=l.nota
                ) for l in src_lines]
                db.add_all(clones); db.commit()
            return new.proyeccion_id

    # Crear borrador vacío
    new = Proyeccion(
        ciclo_id=ciclo_id,
        version=f"draft-{int(datetime.utcnow().timestamp())}",
        descripcion="Borrador automático",
        status=ProyeccionStatusEnum.b,
        is_current=False,
    )
    db.add(new); db.commit(); db.refresh(new)
    return new.proyeccion_id

def apply_event_on_borrador(db: Session, proyeccion_id: int, evento: str, payload: Dict[str, Any]) -> None:
    # Por ahora no-op (no fallar en producción). Aquí podrías:
    # - ajustar líneas cuando cambian fechas/overrides/siembra_confirmada
    # - registrar un event log
    return

def bootstrap_from_plan(
    db: Session,
    ciclo_id: int,
    plan_payload: Dict[str, Any],
    siembras_payload: List[Dict[str, Any]],
) -> Optional[int]:
    if not getattr(settings, "PROYECCION_HOOKS_ENABLED", True) or not getattr(settings, "PROYECCION_BOOTSTRAP_ON_PLAN_CREATE", True):
        return None
    if hay_publicada(db, ciclo_id):
        return None
    # import diferido para evitar ciclos
    from services.proyeccion_service import bootstrap_from_plan as _svc_bootstrap
    # Usuario/roles no vienen aquí; haz un bootstrap “técnico”
    class _SysUser:  # mínimo para atribuir created_by si aplica
        usuario_id = 0
    # Se asume granja disponible via ciclo->granja; no se valida aquí
    proy = _svc_bootstrap(db=db, user=_SysUser(), granja_id=0, ciclo_id=ciclo_id, version="plan-auto", descripcion="Proyección desde plan (adapter)")
    return proy.proyeccion_id if proy else None
