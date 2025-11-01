from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException, status

from models.cycle import Ciclo
from models.farm import Granja
from schemas.cycle import CycleCreate, CycleUpdate, CycleClose


def create_cycle(db: Session, granja_id: int, payload: CycleCreate) -> Ciclo:
    """
    Crea un nuevo ciclo para la granja.

    Validaciones:
    - La granja debe existir y estar activa
    - No puede haber otro ciclo activo en la misma granja
    """
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
    """
    Obtiene el ciclo activo de una granja.

    Returns:
        Ciclo activo o None si no existe
    """
    return db.query(Ciclo).filter(
        and_(Ciclo.granja_id == granja_id, Ciclo.status == "a")
    ).first()


def list_cycles(db: Session, granja_id: int, include_terminated: bool = False) -> list[Ciclo]:
    """
    Lista ciclos de una granja.

    Args:
        granja_id: ID de la granja
        include_terminated: Si True, incluye ciclos terminados

    Returns:
        Lista de ciclos ordenados por fecha de inicio (más reciente primero)
    """
    q = db.query(Ciclo).filter(Ciclo.granja_id == granja_id)
    if not include_terminated:
        q = q.filter(Ciclo.status == "a")
    return q.order_by(Ciclo.fecha_inicio.desc()).all()


def get_cycle(db: Session, ciclo_id: int) -> Ciclo:
    """
    Obtiene un ciclo por ID.

    Raises:
        HTTPException 404: Si el ciclo no existe
    """
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    return cycle


def update_cycle(db: Session, ciclo_id: int, payload: CycleUpdate) -> Ciclo:
    """
    Actualiza un ciclo.

    Validaciones:
    - No se pueden editar ciclos cerrados
    """
    cycle = get_cycle(db, ciclo_id)

    if cycle.status == "c":
        raise HTTPException(status_code=400, detail="No se puede editar un ciclo cerrado")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(cycle, k, v)

    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def close_cycle(db: Session, ciclo_id: int, payload: CycleClose) -> Ciclo:
    """
    Cierra el ciclo.

    Efectos:
    - Cambia status de 'a' → 'c' (cerrado)
    - Registra fecha_cierre_real
    - Actualiza observaciones (opcional)
    - Es irreversible

    Nota: Las métricas del ciclo (toneladas, sobrevivencia, etc.) se calculan
    on-demand desde las tablas operativas (siembras, biometrías, cosechas).
    Ya no se crea registro en CicloResumen.

    Validaciones:
    - El ciclo no debe estar ya cerrado
    """
    cycle = get_cycle(db, ciclo_id)

    if cycle.status == "c":
        raise HTTPException(status_code=400, detail="El ciclo ya está cerrado")

    # Cerrar ciclo
    cycle.status = "c"
    cycle.fecha_cierre_real = payload.fecha_cierre_real

    # Actualizar observaciones si se proporcionan
    if payload.observaciones is not None:
        cycle.observaciones = payload.observaciones

    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle