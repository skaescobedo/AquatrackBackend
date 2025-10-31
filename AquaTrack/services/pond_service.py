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


def _pond_has_history(db: Session, estanque_id: int) -> bool:
    """Verifica si el estanque tiene datos históricos (siembras, biometrías, cosechas)"""
    from models.seeding import SiembraEstanque
    from models.biometria import Biometria
    from models.harvest import CosechaEstanque

    # Verificar siembras
    has_seeding = db.query(SiembraEstanque).filter(
        SiembraEstanque.estanque_id == estanque_id
    ).first() is not None

    if has_seeding:
        return True

    # Verificar biometrías
    has_biometria = db.query(Biometria).filter(
        Biometria.estanque_id == estanque_id
    ).first() is not None

    if has_biometria:
        return True

    # Verificar cosechas
    has_harvest = db.query(CosechaEstanque).filter(
        CosechaEstanque.estanque_id == estanque_id
    ).first() is not None

    return has_harvest


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


def list_ponds_by_farm(db: Session, granja_id: int, vigentes_only: bool = False) -> list[Estanque]:
    ensure_farm_exists(db, granja_id)
    query = db.query(Estanque).filter(Estanque.granja_id == granja_id)

    if vigentes_only:
        query = query.filter(Estanque.is_vigente == True)

    return query.order_by(Estanque.estanque_id.asc()).all()


def get_pond(db: Session, estanque_id: int) -> Estanque:
    pond = db.get(Estanque, estanque_id)
    if not pond:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estanque no encontrado")
    return pond


def update_pond(db: Session, estanque_id: int, payload: PondUpdate) -> Estanque:
    """
    Actualiza un estanque con detección de cambios críticos.

    Si se cambia superficie_m2 sin requires_new_version=True:
    - Retorna 409 con instrucciones de confirmación

    Si se cambia superficie_m2 con requires_new_version=True:
    - Marca estanque actual como is_vigente=False
    - Crea nuevo estanque con nueva superficie
    - Retorna el nuevo estanque
    """
    pond = get_pond(db, estanque_id)
    farm = ensure_farm_exists(db, pond.granja_id)

    data = payload.model_dump(exclude_unset=True)

    # Detectar cambio de superficie
    superficie_nueva = data.get("superficie_m2")
    cambia_superficie = superficie_nueva is not None and superficie_nueva != pond.superficie_m2

    # Si cambia superficie y tiene historial, requiere confirmación
    if cambia_superficie:
        tiene_historial = _pond_has_history(db, estanque_id)

        if tiene_historial and not payload.requires_new_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "type": "critical_change_requires_confirmation",
                    "message": "Cambiar la superficie de un estanque con historial creará una nueva versión",
                    "changes": {
                        "superficie_m2": {
                            "old": float(pond.superficie_m2),
                            "new": float(superficie_nueva)
                        }
                    },
                    "action_required": "Para confirmar, envía requires_new_version=true en el payload"
                }
            )

        # Si confirma o no tiene historial, crear nueva versión
        if tiene_historial and payload.requires_new_version:
            return _create_new_version(db, pond, payload, farm)

    # Cambios simples (nombre, notas) - actualización normal
    if "nombre" in data:
        pond.nombre = data["nombre"]

    if "notas" in data:
        pond.notas = data["notas"]

    if "superficie_m2" in data and not cambia_superficie:
        # Solo si no hay cambio real de superficie (ej: mismo valor)
        pond.superficie_m2 = data["superficie_m2"]

    # Si cambia superficie sin historial, permitir actualización directa
    if cambia_superficie and not _pond_has_history(db, estanque_id):
        # Validar límite de granja
        suma_sin_este = _sum_vigente_surface(db, pond.granja_id, exclude_estanque_id=pond.estanque_id)
        nueva_suma = suma_sin_este + superficie_nueva

        if pond.is_vigente and nueva_suma > farm.superficie_total_m2:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"La suma de estanques vigentes ({nueva_suma}) excede la superficie de la granja ({farm.superficie_total_m2})."
            )

        pond.superficie_m2 = superficie_nueva

    db.add(pond)
    db.commit()
    db.refresh(pond)
    return pond


def _create_new_version(db: Session, old_pond: Estanque, payload: PondUpdate, farm: Granja) -> Estanque:
    """
    Crea una nueva versión del estanque cuando cambia la superficie.

    - Marca el antiguo como is_vigente=False
    - Crea uno nuevo con la nueva superficie
    """
    data = payload.model_dump(exclude_unset=True)
    nueva_superficie = data.get("superficie_m2", old_pond.superficie_m2)
    nuevo_nombre = data.get("nombre", old_pond.nombre)

    # Validar límite de granja (el nuevo será vigente, el viejo no)
    suma_sin_viejo = _sum_vigente_surface(db, old_pond.granja_id, exclude_estanque_id=old_pond.estanque_id)
    nueva_suma = suma_sin_viejo + nueva_superficie

    if nueva_suma > farm.superficie_total_m2:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La nueva versión excede la superficie de la granja: {nueva_suma} > {farm.superficie_total_m2}"
        )

    # Marcar viejo como no vigente
    old_pond.is_vigente = False
    notas_old = old_pond.notas or ""
    old_pond.notas = f"{notas_old} | Reemplazado por nueva versión (cambio de superficie)".strip()
    db.add(old_pond)
    db.flush()

    # Crear nuevo estanque
    new_pond = Estanque(
        granja_id=old_pond.granja_id,
        nombre=nuevo_nombre,
        superficie_m2=nueva_superficie,
        status='d',  # disponible (puede ser usado en nuevos ciclos)
        is_vigente=True,
        notas=f"Nueva versión de estanque_id={old_pond.estanque_id}. {data.get('notas', '')}".strip()
    )
    db.add(new_pond)
    db.commit()
    db.refresh(new_pond)

    return new_pond


def delete_pond(db: Session, estanque_id: int) -> dict:
    """
    Elimina un estanque de forma inteligente:

    - Si tiene historial (siembras, biometrías, cosechas):
      * Soft delete: marca is_vigente=False
      * Retorna info sobre soft delete

    - Si NO tiene historial:
      * Hard delete: elimina físicamente el registro
      * Retorna None (204)
    """
    pond = get_pond(db, estanque_id)

    tiene_historial = _pond_has_history(db, estanque_id)

    if tiene_historial:
        # Soft delete
        pond.is_vigente = False
        notas_old = pond.notas or ""
        pond.notas = f"{notas_old} | Eliminado (soft delete - preserva historial)".strip()
        db.add(pond)
        db.commit()

        return {
            "deleted": False,
            "soft_deleted": True,
            "estanque_id": estanque_id,
            "message": "Estanque marcado como no vigente (tiene historial)"
        }
    else:
        # Hard delete
        db.delete(pond)
        db.commit()

        return {
            "deleted": True,
            "soft_deleted": False,
            "estanque_id": estanque_id,
            "message": "Estanque eliminado permanentemente (sin historial)"
        }