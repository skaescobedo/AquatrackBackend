# ============================================================================
# SERVICES: services/farm_service.py
# ============================================================================

from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from models.farm import Granja
from models.pond import Estanque
from models.user import Usuario, UsuarioGranja
from schemas.farm import FarmCreate, FarmUpdate


def list_farms(db: Session, current_user: Usuario) -> list[Granja]:
    """
    Listar granjas según permisos del usuario.

    - Admin Global: Ve todas las granjas
    - Usuario normal: Ve solo las granjas donde tiene membership activo
    """
    if current_user.is_admin_global:
        return db.query(Granja).order_by(Granja.nombre.asc()).all()

    # Usuario normal: solo sus granjas con membership activo
    granja_ids = (
        db.query(UsuarioGranja.granja_id)
        .filter(
            UsuarioGranja.usuario_id == current_user.usuario_id,
            UsuarioGranja.status == "a"
        )
        .all()
    )
    ids = [g[0] for g in granja_ids]

    if not ids:
        return []

    return (
        db.query(Granja)
        .filter(Granja.granja_id.in_(ids))
        .order_by(Granja.nombre.asc())
        .all()
    )


def _sum_vigente_surface(db: Session, granja_id: int, exclude_estanque_id: int | None = None) -> Decimal:
    """Suma la superficie de estanques vigentes de una granja."""
    q = (
        db.query(func.coalesce(func.sum(Estanque.superficie_m2), 0))
        .filter(Estanque.granja_id == granja_id, Estanque.is_vigente.is_(True))
    )
    if exclude_estanque_id is not None:
        q = q.filter(Estanque.estanque_id != exclude_estanque_id)
    total = q.scalar()  # Numeric -> Decimal
    return total or Decimal("0")


def create_farm(db: Session, payload: FarmCreate) -> Granja:
    """
    Crear una nueva granja con validación de superficie.

    Solo Admin Global puede crear granjas.
    """
    try:
        farm = Granja(
            nombre=payload.nombre,
            ubicacion=payload.ubicacion,
            descripcion=payload.descripcion,
            superficie_total_m2=payload.superficie_total_m2,
            is_active=True,
        )
        db.add(farm)
        db.flush()  # granja_id

        # Validación de superficie para estanques anidados (solo los vigentes)
        if payload.estanques:
            sum_nested_vigentes = sum(
                (p.superficie_m2 for p in payload.estanques if bool(p.is_vigente)),
                start=Decimal("0"),
            )
            if sum_nested_vigentes > farm.superficie_total_m2:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Suma de estanques vigentes ({sum_nested_vigentes}) excede la superficie de la granja ({farm.superficie_total_m2}).",
                )

            ponds = [
                Estanque(
                    granja_id=farm.granja_id,
                    nombre=p.nombre,
                    superficie_m2=p.superficie_m2,
                    status="i",  # siempre 'i' al crear
                    is_vigente=bool(p.is_vigente),
                )
                for p in payload.estanques
            ]
            db.add_all(ponds)

        db.commit()
        db.refresh(farm)
        return farm
    except Exception:
        db.rollback()
        raise


# En AquaTrack/services/farm_service.py

def update_farm(db: Session, granja_id: int, payload: FarmUpdate) -> Granja:
    """
    Actualizar una granja existente.

    Valida que la nueva superficie no sea menor a la suma de estanques vigentes.
    Valida que no se pueda desactivar si hay ciclo activo.
    """
    from models.cycle import Ciclo  # Import local para evitar dependencia circular

    farm = db.get(Granja, granja_id)
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Granja no encontrada")

    data = payload.model_dump(exclude_unset=True)

    # NUEVA VALIDACIÓN: No permitir desactivar granja con ciclo activo
    if "is_active" in data and data["is_active"] is False and farm.is_active:
        # Verificar si hay ciclo activo
        ciclo_activo = db.query(Ciclo).filter(
            Ciclo.granja_id == granja_id,
            Ciclo.status == 'a'
        ).first()

        if ciclo_activo:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No se puede desactivar la granja porque tiene un ciclo activo: {ciclo_activo.nombre}. Primero debes cerrar el ciclo."
            )

    # Si cambia la superficie_total_m2, validar que no quede por debajo de la suma vigente actual
    if "superficie_total_m2" in data and data["superficie_total_m2"] is not None:
        nueva_superficie: Decimal = data["superficie_total_m2"]
        suma_vigentes = _sum_vigente_surface(db, granja_id)
        if suma_vigentes > nueva_superficie:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No puede reducir la superficie a {nueva_superficie}; los estanques vigentes suman {suma_vigentes}.",
            )

    for k, v in data.items():
        setattr(farm, k, v)

    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


def get_farm(db: Session, granja_id: int) -> Granja:
    """
    Obtener una granja por ID.

    Returns:
        Granja encontrada

    Raises:
        HTTPException 404: Si la granja no existe
    """
    farm = db.get(Granja, granja_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Granja no encontrada"
        )
    return farm