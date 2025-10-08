# services/sob_utils.py
from sqlalchemy.orm import Session
from models.sob_cambio_log import SobCambioLog
from enums.enums import SobFuenteEnum

def get_sob_actual_pct(db: Session, ciclo_id: int, estanque_id: int) -> float | None:
    row = (
        db.query(SobCambioLog.sob_nueva_pct)
        .filter(SobCambioLog.ciclo_id == ciclo_id, SobCambioLog.estanque_id == estanque_id)
        .order_by(SobCambioLog.changed_at.desc(), SobCambioLog.sob_cambio_log_id.desc())
        .first()
    )
    return float(row[0]) if row else None

def ensure_baseline_sob_100(
    db: Session, *, ciclo_id: int, estanque_id: int, actor_id: int
) -> None:
    """Registra baseline 100% si no hay SOB previo para este estanque en el ciclo."""
    actual = get_sob_actual_pct(db, ciclo_id, estanque_id)
    if actual is None:
        log = SobCambioLog(
            estanque_id=estanque_id,
            ciclo_id=ciclo_id,
            sob_anterior_pct=100.00,
            sob_nueva_pct=100.00,
            fuente=SobFuenteEnum.operativa_actual,
            motivo="baseline siembra confirmada",
            changed_by=actor_id,
        )
        db.add(log)
        # flush opcional si quieres validar FK/constraints antes del commit:
        # db.flush()
