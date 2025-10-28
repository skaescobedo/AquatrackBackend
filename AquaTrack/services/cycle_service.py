from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException, status
from datetime import date

from models.cycle import Ciclo, CicloResumen
from models.farm import Granja
from schemas.cycle import CycleCreate, CycleUpdate, CycleClose


def create_cycle(db: Session, granja_id: int, payload: CycleCreate) -> Ciclo:
    # Validar granja existe y activa
    farm = db.get(Granja, granja_id)
    if not farm or not farm.is_active:
        raise HTTPException(status_code=404, detail="Granja no encontrada o inactiva")

    # Validar que NO haya otro ciclo activo en esa granja
    existing = db.query(Ciclo).filter(
        and_(Ciclo.granja_id == granja_id, Ciclo.status == "a")
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un ciclo activo para esta granja: {existing.nombre}"
        )

    cycle = Ciclo(
        granja_id=granja_id,
        nombre=payload.nombre,
        fecha_inicio=payload.fecha_inicio,
        fecha_fin_planificada=payload.fecha_fin_planificada,
        observaciones=payload.observaciones,
        status="a"
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def get_active_cycle(db: Session, granja_id: int) -> Ciclo | None:
    return db.query(Ciclo).filter(
        and_(Ciclo.granja_id == granja_id, Ciclo.status == "a")
    ).first()


def list_cycles(db: Session, granja_id: int, include_terminated: bool = False) -> list[Ciclo]:
    q = db.query(Ciclo).filter(Ciclo.granja_id == granja_id)
    if not include_terminated:
        q = q.filter(Ciclo.status == "a")
    return q.order_by(Ciclo.fecha_inicio.desc()).all()


def get_cycle(db: Session, ciclo_id: int) -> Ciclo:
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    return cycle


def update_cycle(db: Session, ciclo_id: int, payload: CycleUpdate) -> Ciclo:
    cycle = get_cycle(db, ciclo_id)

    if cycle.status == "t":
        raise HTTPException(status_code=400, detail="No se puede editar un ciclo terminado")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(cycle, k, v)

    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def close_cycle(
        db: Session,
        ciclo_id: int,
        payload: CycleClose,
        sob_final: float,
        toneladas: float,
        n_estanques: int
) -> Ciclo:
    """
    Cierra el ciclo y congela resumen.
    Los valores sob_final, toneladas, n_estanques se calcularán en el futuro
    desde calculation_service. Por ahora los recibimos como params mock.
    """
    cycle = get_cycle(db, ciclo_id)

    if cycle.status == "t":
        raise HTTPException(status_code=400, detail="El ciclo ya está cerrado")

    # Cerrar ciclo
    cycle.status = "t"
    cycle.fecha_cierre_real = payload.fecha_cierre_real

    # Crear resumen
    resumen = CicloResumen(
        ciclo_id=cycle.ciclo_id,
        sob_final_real_pct=sob_final,
        toneladas_cosechadas=toneladas,
        n_estanques_cosechados=n_estanques,
        fecha_inicio_real=cycle.fecha_inicio,
        fecha_fin_real=payload.fecha_cierre_real,
        notas_cierre=payload.notas_cierre
    )

    db.add(cycle)
    db.add(resumen)
    db.commit()
    db.refresh(cycle)
    return cycle