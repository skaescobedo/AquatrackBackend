# services/_proy_integration.py
from __future__ import annotations
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from config.settings import settings
from services import proyeccion_adapter as adapter

def proy_touch_borrador_event(
    db: Session,
    *,
    ciclo_id: int,
    actor_id: int,
    event: str,
    payload: Dict[str, Any] | None = None,
) -> Optional[int]:
    """
    - Respeta flags de settings:
      - PROYECCION_HOOKS_ENABLED (se usa en adapter)
      - PROYECCION_AUTO_CREATE_ON_MUTATIONS (apagado = no hace nada)
      - PROYECCION_STRICT_FAIL (si True, propaga excepciones)
    - Devuelve proyeccion_id si hubo borrador (nuevo o existente).
    """
    if not getattr(settings, "PROYECCION_AUTO_CREATE_ON_MUTATIONS", True):
        return None

    try:
        proy_id = adapter.get_or_create_borrador(db, ciclo_id=ciclo_id)
        if proy_id is not None:
            adapter.apply_event_on_borrador(
                db,
                proyeccion_id=proy_id,
                evento=event,
                payload=payload or {},
            )
        return proy_id
    except Exception:
        if getattr(settings, "PROYECCION_STRICT_FAIL", False):
            raise
        return None
