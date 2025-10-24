# services/biometry_service.py
from __future__ import annotations
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func, select
from models.usuario import Usuario
from models.ciclo import Ciclo
from models.estanque import Estanque
from models.biometria import Biometria
from models.sob_cambio_log import SobCambioLog
from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from services.permissions_service import ensure_user_in_farm_or_admin

# Hook: modo FIN DE SEMANA con cobertura y ponderación
from services.reforecast_live_service import observe_and_rebuild_from_weekend_window_hook_safe

# --- helpers ---

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _today_local_date() -> date:
    return datetime.utcnow().date()

def _pp_g_from_sample(n_muestra: int, peso_muestra_g: Decimal) -> Decimal:
    if n_muestra <= 0:
        raise HTTPException(status_code=422, detail="invalid_n_muestra")
    return (peso_muestra_g / Decimal(n_muestra)).quantize(Decimal("0.001"))

def _last_biometry(db: Session, ciclo_id: int, estanque_id: int) -> Optional[Biometria]:
    return (
        db.query(Biometria)
        .filter(Biometria.ciclo_id == ciclo_id, Biometria.estanque_id == estanque_id)
        .order_by(desc(Biometria.created_at))
        .first()
    )

def _current_operational_sob(db: Session, ciclo_id: int, estanque_id: int, today: date) -> tuple[Optional[Decimal], str | None]:
    # 1) último log de SOB
    last_log = (
        db.query(SobCambioLog)
        .filter(SobCambioLog.ciclo_id == ciclo_id, SobCambioLog.estanque_id == estanque_id)
        .order_by(desc(SobCambioLog.changed_at))
        .first()
    )
    if last_log:
        return (Decimal(str(last_log.sob_nueva_pct)), 'operativa_actual')

    # 2) proyección vigente (orden compatible con MySQL)
    proj = (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id)
        .order_by(
            desc(Proyeccion.is_current),
            Proyeccion.published_at.is_(None).asc(),
            desc(Proyeccion.published_at),
            desc(Proyeccion.created_at),
        )
        .first()
    )
    if proj:
        line = (
            db.query(ProyeccionLinea)
            .filter(ProyeccionLinea.proyeccion_id == proj.proyeccion_id, ProyeccionLinea.fecha_plan <= today)
            .order_by(desc(ProyeccionLinea.fecha_plan))
            .first()
        )
        if not line:
            line = (
                db.query(ProyeccionLinea)
                .filter(ProyeccionLinea.proyeccion_id == proj.proyeccion_id)
                .order_by(asc(ProyeccionLinea.fecha_plan))
                .first()
            )
        if line:
            return (Decimal(str(line.sob_pct_linea)), 'reforecast')

    return (None, None)

# --- comandos ---

def create_biometry(
    db: Session,
    user: Usuario,
    ciclo_id: int,
    body,
):
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    pond = db.get(Estanque, body.estanque_id)
    if not pond or pond.granja_id != ciclo.granja_id:
        raise HTTPException(status_code=404, detail="pond_not_found_in_farm")

    today = _today_local_date()
    now = _now_utc()

    try:
        peso_total = Decimal(str(body.peso_muestra_g))
    except InvalidOperation:
        raise HTTPException(status_code=422, detail="invalid_peso_muestra_g")

    pp_g = _pp_g_from_sample(int(body.n_muestra), peso_total)

    last = _last_biometry(db, ciclo_id, pond.estanque_id)
    incremento = None
    if last:
        try:
            incremento = (Decimal(str(pp_g)) - Decimal(str(last.pp_g))).quantize(Decimal("0.001"))
        except InvalidOperation:
            incremento = None

    default_sob, default_source = _current_operational_sob(db, ciclo_id, pond.estanque_id, today)

    requested_sob = None if body.sob_usada_pct is None else Decimal(str(body.sob_usada_pct)).quantize(Decimal("0.01"))

    actualiza = 0
    sob_fuente = default_source
    if requested_sob is None:
        if default_sob is None:
            raise HTTPException(status_code=422, detail="sob_missing_and_no_default")
        sob_to_use = default_sob
    else:
        if (default_sob is None) or (requested_sob != default_sob):
            anterior = default_sob if default_sob is not None else Decimal("0.00")
            log = SobCambioLog(
                estanque_id=pond.estanque_id,
                ciclo_id=ciclo_id,
                sob_anterior_pct=anterior,
                sob_nueva_pct=requested_sob,
                fuente='ajuste_manual',
                motivo="Ajuste manual desde captura de biometría",
                changed_by=user.usuario_id,
            )
            db.add(log)
            actualiza = 1
            sob_fuente = 'ajuste_manual'
            sob_to_use = requested_sob
        else:
            sob_to_use = default_sob

    bio = Biometria(
        ciclo_id=ciclo_id,
        estanque_id=pond.estanque_id,
        fecha=today,
        n_muestra=int(body.n_muestra),
        peso_muestra_g=peso_total,
        pp_g=pp_g,
        sob_usada_pct=sob_to_use,
        incremento_g_sem=incremento,
        notas=body.notas,
        actualiza_sob_operativa=actualiza,
        sob_fuente=sob_fuente,
        created_by=user.usuario_id,
    )
    db.add(bio)
    db.commit()
    db.refresh(bio)

    # ---- HOOK: fin de semana, cobertura ≥30%, anclar en DOMINGO ----
    try:
        observe_and_rebuild_from_weekend_window_hook_safe(
            db, user, ciclo_id,
            event_date=bio.fecha,     # tomamos el fin de semana de esa fecha
            coverage_threshold=0.30,  # 30% de estanques medidos
            min_ponds=1,              # sube si quieres exigir mínimo N estanques
            reason="bio_weekend_agg",
        )
    except Exception:
        # no interrumpir operación si algo falla
        pass

    return bio


def list_biometry(
    db: Session,
    user: Usuario,
    ciclo_id: int,
    estanque_id: Optional[int] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
) -> List[Biometria]:
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    q = db.query(Biometria).filter(Biometria.ciclo_id == ciclo_id)
    if estanque_id:
        q = q.filter(Biometria.estanque_id == estanque_id)
    if created_from:
        q = q.filter(Biometria.created_at >= created_from)
    if created_to:
        q = q.filter(Biometria.created_at <= created_to)

    q = q.order_by(asc(Biometria.created_at))
    return q.all()
