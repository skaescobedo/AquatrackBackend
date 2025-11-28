# services/pond_service.py
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from models.farm import Granja
from models.pond import Estanque
from models.cycle import Ciclo
from models.seeding import SiembraPlan, SiembraEstanque
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
    """
    Verifica si el estanque tiene historial operativo de ciclos PASADOS.

    Historial = Siembras confirmadas (status='f') en ciclos NO activos.

    Esto determina si se debe crear una nueva versión del estanque
    al cambiar la superficie (para preservar trazabilidad histórica).

    Nota: Siembras confirmadas en ciclo activo se validan por separado
    con _pond_has_confirmed_seeding_in_active_cycle() para bloquear edición.
    """
    has_historical_seeding = (
                                 db.query(SiembraEstanque)
                                 .join(SiembraPlan, SiembraPlan.siembra_plan_id == SiembraEstanque.siembra_plan_id)
                                 .join(Ciclo, Ciclo.ciclo_id == SiembraPlan.ciclo_id)
                                 .filter(
                                     SiembraEstanque.estanque_id == estanque_id,
                                     SiembraEstanque.status == 'f',
                                     Ciclo.status != 'a'
                                 )
                                 .first()
                             ) is not None

    return has_historical_seeding


def _pond_has_confirmed_seeding_in_active_cycle(db: Session, estanque_id: int) -> bool:
    """
    Verifica si el estanque tiene siembra confirmada (status='f') en un ciclo activo (status='a').

    Returns:
        True si tiene siembra confirmada en ciclo activo, False en caso contrario
    """
    result = (
        db.query(SiembraEstanque)
        .join(SiembraPlan, SiembraPlan.siembra_plan_id == SiembraEstanque.siembra_plan_id)
        .join(Ciclo, Ciclo.ciclo_id == SiembraPlan.ciclo_id)
        .filter(
            SiembraEstanque.estanque_id == estanque_id,
            SiembraEstanque.status == 'f',
            Ciclo.status == 'a'
        )
        .first()
    )
    return result is not None


def _farm_has_active_cycle_with_confirmed_seeding(db: Session, granja_id: int) -> bool:
    """
    Verifica si la granja tiene algún ciclo activo con siembras confirmadas.

    Returns:
        True si existe ciclo activo con siembras confirmadas, False en caso contrario
    """
    result = (
        db.query(Ciclo)
        .join(SiembraPlan, SiembraPlan.ciclo_id == Ciclo.ciclo_id)
        .join(SiembraEstanque, SiembraEstanque.siembra_plan_id == SiembraPlan.siembra_plan_id)
        .filter(
            Ciclo.granja_id == granja_id,
            Ciclo.status == 'a',
            SiembraEstanque.status == 'f'
        )
        .first()
    )
    return result is not None


def ensure_farm_exists(db: Session, granja_id: int) -> Granja:
    farm = db.get(Granja, granja_id)
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Granja no encontrada")
    if not farm.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La granja está inactiva")
    return farm


def create_pond(db: Session, granja_id: int, payload: PondCreate) -> Estanque:
    farm = ensure_farm_exists(db, granja_id)

    # BLOQUEO SELECTIVO: NO permitir crear estanques si hay ciclo activo con siembras confirmadas
    if _farm_has_active_cycle_with_confirmed_seeding(db, granja_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pueden crear estanques mientras exista un ciclo activo con siembras confirmadas. Esto alteraría datos operativos en curso."
        )

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
        status="i",
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
    Actualiza un estanque con versionamiento automático.

    Cambios simples (nombre, notas):
    - Actualización directa

    Cambio de superficie SIN historial:
    - Actualización directa

    Cambio de superficie CON historial:
    - Crea nueva versión automáticamente
    - Marca estanque actual como is_vigente=False
    - Retorna el nuevo estanque

    BLOQUEOS:
    - NO permite cambiar superficie si tiene siembra confirmada en ciclo activo
    """
    pond = get_pond(db, estanque_id)
    farm = ensure_farm_exists(db, pond.granja_id)

    data = payload.model_dump(exclude_unset=True)

    # Detectar cambio de superficie
    superficie_nueva = data.get("superficie_m2")
    cambia_superficie = superficie_nueva is not None and superficie_nueva != pond.superficie_m2

    # BLOQUEO: validar si estanque tiene siembra confirmada en ciclo activo
    if cambia_superficie and _pond_has_confirmed_seeding_in_active_cycle(db, estanque_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede cambiar la superficie de un estanque con siembra confirmada en un ciclo activo. Esto alteraría datos operativos en curso."
        )

    # Si cambia superficie y tiene historial → crear nueva versión automáticamente
    if cambia_superficie:
        tiene_historial = _pond_has_history(db, estanque_id)

        if tiene_historial:
            return _create_new_version(db, pond, payload, farm)

    # Cambios simples - actualización normal
    if "nombre" in data:
        pond.nombre = data["nombre"]

    if "notas" in data:
        pond.notas = data["notas"]

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
    db.add(old_pond)
    db.flush()

    # Crear nuevo estanque
    new_pond = Estanque(
        granja_id=old_pond.granja_id,
        nombre=nuevo_nombre,
        superficie_m2=nueva_superficie,
        status='i',
        is_vigente=True,
    )
    db.add(new_pond)
    db.commit()
    db.refresh(new_pond)

    return new_pond


def delete_pond(db: Session, estanque_id: int) -> dict:
    """
    Elimina un estanque de forma inteligente:

    - Si tiene historial (siembras confirmadas en ciclos pasados):
      * Soft delete: marca is_vigente=False
      * Retorna info sobre soft delete

    - Si NO tiene historial:
      * Hard delete: elimina físicamente el registro
      * Retorna dict con info

    BLOQUEO:
    - NO permite eliminar si tiene siembra confirmada en ciclo activo
    """
    pond = get_pond(db, estanque_id)

    # BLOQUEO: validar si estanque tiene siembra confirmada en ciclo activo
    if _pond_has_confirmed_seeding_in_active_cycle(db, estanque_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar un estanque con siembra confirmada en un ciclo activo. Esto alteraría datos operativos en curso."
        )

    tiene_historial = _pond_has_history(db, estanque_id)

    if tiene_historial:
        # Soft delete
        pond.is_vigente = False
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