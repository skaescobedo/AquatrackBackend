from datetime import date
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.ciclo import Ciclo
from models.proyeccion import Proyeccion
from models.granja import Granja
from schemas.ciclo import CicloCreate
from services.permissions_service import ensure_user_in_farm_or_admin
from services.projection_ingest_service import ingest_from_file
from models.usuario import Usuario

def _ensure_one_active_per_farm(db: Session, granja_id: int):
    # Confía en constraint de la BD; aquí solo adelantamos el error si detectamos
    cnt = db.query(Ciclo).filter(Ciclo.granja_id == granja_id, Ciclo.estado == "a").count()
    if cnt > 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="active_cycle_already_exists_for_farm")

def create_cycle(
    db: Session,
    user: Usuario,
    granja_id: int,
    body: CicloCreate,
) -> tuple[Ciclo, int | None]:
    # acceso
    ensure_user_in_farm_or_admin(db, user, granja_id)

    # granja debe existir
    if not db.get(Granja, granja_id):
        raise HTTPException(status_code=404, detail="farm_not_found")

    _ensure_one_active_per_farm(db, granja_id)

    c = Ciclo(
        granja_id=granja_id,
        nombre=body.nombre,
        fecha_inicio=body.fecha_inicio,
        fecha_fin_planificada=body.fecha_fin_planificada,
        estado="a",
        observaciones=body.observaciones,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    draft_id: int | None = None
    if getattr(body, "archivo_id", None):
        # seguridad: no permitir si ya hay borrador (no debería existir en ciclo recién creado)
        existing_draft = (
            db.query(Proyeccion)
            .filter(Proyeccion.ciclo_id == c.ciclo_id, Proyeccion.status == "b")
            .first()
        )
        if existing_draft:
            raise HTTPException(status_code=409, detail="draft_projection_already_exists")

        # NUEVO: usa el servicio con Gemini (devuelve (proyeccion, warnings))
        proy, _warnings = ingest_from_file(
            db,
            user,
            ciclo_id=c.ciclo_id,
            archivo_id=body.archivo_id,
            force_reingest=False,  # respeta idempotencia por checksum+ciclo
        )
        draft_id = proy.proyeccion_id

    return c, draft_id


def list_cycles(db: Session, user: Usuario, granja_id: int, estado: str | None):
    ensure_user_in_farm_or_admin(db, user, granja_id)
    q = db.query(Ciclo).filter(Ciclo.granja_id == granja_id)
    if estado:
        q = q.filter(Ciclo.estado == estado)
    q = q.order_by(Ciclo.created_at.desc())
    return q.all()

def get_cycle(db: Session, user: Usuario, ciclo_id: int) -> Ciclo:
    c = db.get(Ciclo, ciclo_id)
    if not c:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    ensure_user_in_farm_or_admin(db, user, c.granja_id)
    return c
