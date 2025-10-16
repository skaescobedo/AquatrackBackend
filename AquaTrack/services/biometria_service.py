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
from services.reforecast_live_service import observe_and_rebuild_hook_safe  # <-- NUEVO

# --- helpers ---

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _today_local_date() -> date:
    # Si tu server está en UTC y quieres hora local, ajusta aquí
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
    """
    Regresa (sob_pct, fuente_for_biometria) donde fuente_for_biometria ∈ {'operativa_actual','reforecast', None}
    1) Último SOB de sob_cambio_log del estanque+ciclo => (valor, 'operativa_actual')
    2) Si no hay log, intenta de proyección vigente (línea más reciente ≤ today) => (valor, 'reforecast')
    3) Si tampoco hay proyección, (None, None)
    """
    # 1) último log
    last_log = (
        db.query(SobCambioLog)
        .filter(SobCambioLog.ciclo_id == ciclo_id, SobCambioLog.estanque_id == estanque_id)
        .order_by(desc(SobCambioLog.changed_at))
        .first()
    )
    if last_log:
        return (Decimal(str(last_log.sob_nueva_pct)), 'operativa_actual')

    # 2) proyección vigente del ciclo
    proj = (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id)
        .order_by(desc(Proyeccion.is_current),
                  Proyeccion.published_at.is_(None).asc(),
                  desc(Proyeccion.published_at),
                  desc(Proyeccion.created_at))
        .first()
    )
    if proj:
        # línea con fecha_plan <= today, o si ninguna <= hoy, la más cercana
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
    # validaciones de pertenencia
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)

    pond = db.get(Estanque, body.estanque_id)
    if not pond or pond.granja_id != ciclo.granja_id:
        raise HTTPException(status_code=404, detail="pond_not_found_in_farm")

    # fecha de biometría = ahora (fecha) y timestamp en created_at
    today = _today_local_date()
    now = _now_utc()

    # calcular pp_g desde la muestra
    try:
        peso_total = Decimal(str(body.peso_muestra_g))
    except InvalidOperation:
        raise HTTPException(status_code=422, detail="invalid_peso_muestra_g")

    pp_g = _pp_g_from_sample(int(body.n_muestra), peso_total)

    # incremento vs última biometría del estanque en el ciclo
    last = _last_biometry(db, ciclo_id, pond.estanque_id)
    incremento = None
    if last:
        try:
            incremento = (Decimal(str(pp_g)) - Decimal(str(last.pp_g))).quantize(Decimal("0.001"))
        except InvalidOperation:
            incremento = None

    # SOB vigente (operativa o proyección)
    default_sob, default_source = _current_operational_sob(db, ciclo_id, pond.estanque_id, today)

    # SOB enviada (opcional)
    requested_sob = None if body.sob_usada_pct is None else Decimal(str(body.sob_usada_pct)).quantize(Decimal("0.01"))

    # decidir SOB a usar y si hay ajuste manual (log)
    actualiza = 0
    sob_fuente = default_source
    sob_to_use: Decimal

    if requested_sob is None:
        if default_sob is None:
            raise HTTPException(status_code=422, detail="sob_missing_and_no_default")
        sob_to_use = default_sob
        # sob_fuente ya viene: 'operativa_actual' o 'reforecast'
    else:
        if (default_sob is None) or (requested_sob != default_sob):
            # ajuste manual
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
            # coincide con la operativa vigente
            sob_to_use = default_sob
            # sob_fuente se queda como default_source

    # crear biometría
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

    # ---- HOOK: actualizar reforecast vivo (suave, no romper flujo) ----
    try:
        set_pp = float(bio.pp_g) if bio.pp_g is not None else None
        set_sob = float(bio.sob_usada_pct) if bio.sob_usada_pct is not None else None
        observe_and_rebuild_hook_safe(
            db, user, ciclo_id,
            event_date=bio.fecha,
            set_pp=set_pp,
            set_sob=set_sob,
            reason="bio",
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

    # Orden más útil: por created_at asc (cronológico)
    q = q.order_by(asc(Biometria.created_at))
    return q.all()
