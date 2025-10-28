from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from models.farm import Granja
from models.pond import Estanque
from schemas.pond import PondCreate, PondUpdate

def _sum_vigente_surface(db: Session, granja_id: int, exclude_estanque_id: int | None = None) -> Decimal:
    q = (
        db.query(func.coalesce(func.sum(Estanque.superficie_m2), 0))
        .filter(Estanque.granja_id == granja_id, Estanque.is_vigente.is_(True))
    )
    if exclude_estanque_id is not None:
        q = q.filter(Estanque.estanque_id != exclude_estanque_id)
    total = q.scalar()
    return total or Decimal("0")

def ensure_farm_exists(db: Session, granja_id: int) -> Granja:
    farm = db.get(Granja, granja_id)
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Granja no encontrada")
    if not farm.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La granja está inactiva")
    return farm

def create_pond(db: Session, granja_id: int, payload: PondCreate) -> Estanque:
    farm = ensure_farm_exists(db, granja_id)

    # Validación de superficie (considerando solo vigentes)
    if bool(payload.is_vigente):
        suma_vigentes = _sum_vigente_surface(db, granja_id)
        nueva_suma = suma_vigentes + payload.superficie_m2
        if nueva_suma > farm.superficie_total_m2:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Crear este estanque vigente excede la superficie de la granja: {nueva_suma} > {farm.superficie_total_m2}.",
            )

    pond = Estanque(
        granja_id=granja_id,
        nombre=payload.nombre,
        superficie_m2=payload.superficie_m2,
        status="i",  # siempre inactivo al crear
        is_vigente=bool(payload.is_vigente),
    )
    db.add(pond)
    db.commit()
    db.refresh(pond)
    return pond

def list_ponds_by_farm(db: Session, granja_id: int) -> list[Estanque]:
    ensure_farm_exists(db, granja_id)
    return (
        db.query(Estanque)
        .filter(Estanque.granja_id == granja_id)
        .order_by(Estanque.estanque_id.asc())
        .all()
    )

def get_pond(db: Session, estanque_id: int) -> Estanque:
    pond = db.get(Estanque, estanque_id)
    if not pond:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estanque no encontrado")
    return pond

def update_pond(db: Session, estanque_id: int, payload: PondUpdate) -> Estanque:
    pond = get_pond(db, estanque_id)
    farm = ensure_farm_exists(db, pond.granja_id)

    data = payload.model_dump(exclude_unset=True)

    # Calcula los valores "nuevos" propuestos para validar correctamente
    nueva_superficie: Decimal = data.get("superficie_m2", pond.superficie_m2)
    nuevo_vigente: bool = data.get("is_vigente", pond.is_vigente)

    # Si el estanque resultará vigente, verificar que la suma (excluyéndolo) + su nueva superficie no exceda
    if nuevo_vigente:
        suma_sin_este = _sum_vigente_surface(db, pond.granja_id, exclude_estanque_id=pond.estanque_id)
        nueva_suma = suma_sin_este + nueva_superficie
        if nueva_suma > farm.superficie_total_m2:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"La suma de estanques vigentes ({nueva_suma}) excede la superficie de la granja ({farm.superficie_total_m2}).",
            )

    # Aplicar cambios permitidos (no se cambia 'status' aquí)
    for k, v in data.items():
        setattr(pond, k, v)

    db.add(pond)
    db.commit()
    db.refresh(pond)
    return pond
