# services/harvest_service.py
from __future__ import annotations
from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from fastapi import HTTPException, status

from utils.datetime_utils import today_mazatlan
from models.cycle import Ciclo
from models.farm import Granja
from models.pond import Estanque
from models.seeding import SiembraPlan, SiembraEstanque
from models.harvest import CosechaOla, CosechaEstanque
from schemas.harvest import HarvestWaveCreate


def _get_cycle_and_farm(db: Session, ciclo_id: int) -> tuple[Ciclo, Granja]:
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    farm = db.get(Granja, cycle.granja_id)
    if not farm or not farm.is_active:
        raise HTTPException(status_code=409, detail="La granja del ciclo no existe o está inactiva")
    return cycle, farm


def _next_order(db: Session, ciclo_id: int) -> int:
    current_max = db.query(func.max(CosechaOla.orden)).filter(CosechaOla.ciclo_id == ciclo_id).scalar()
    return int(current_max or 0) + 1


def create_wave_and_autolines(
    db: Session,
    ciclo_id: int,
    payload: HarvestWaveCreate,
    created_by_user_id: int | None,
) -> CosechaOla:
    cycle, farm = _get_cycle_and_farm(db, ciclo_id)

    # Crear ola
    ola = CosechaOla(
        ciclo_id=ciclo_id,
        nombre=payload.nombre,
        tipo=payload.tipo,
        ventana_inicio=payload.ventana_inicio,
        ventana_fin=payload.ventana_fin,
        objetivo_retiro_org_m2=payload.objetivo_retiro_org_m2,
        status="p",
        orden=payload.orden if payload.orden is not None else _next_order(db, ciclo_id),
        notas=payload.notas,
        created_by=created_by_user_id
    )
    db.add(ola)
    db.flush()  # obtener cosecha_ola_id

    # Estanques candidatos: solo con **siembra confirmada** en este ciclo
    # (y opcionalmente vigentes)
    seeded_ponds = (
        db.query(Estanque)
        .join(SiembraEstanque, and_(
            SiembraEstanque.estanque_id == Estanque.estanque_id,
            SiembraEstanque.status == "f"
        ))
        .join(SiembraPlan, and_(
            SiembraPlan.siembra_plan_id == SiembraEstanque.siembra_plan_id,
            SiembraPlan.ciclo_id == ciclo_id
        ))
        .filter(Estanque.granja_id == farm.granja_id)
        .order_by(Estanque.estanque_id.asc())
        .all()
    )

    pond_ids = [p.estanque_id for p in seeded_ponds]
    total = len(pond_ids)

    cosechas: list[CosechaEstanque] = []
    if total > 0:
        days = (payload.ventana_fin - payload.ventana_inicio).days
        for idx, pond_id in enumerate(pond_ids):
            if days <= 0:
                fecha = payload.ventana_inicio
            else:
                step = round((days * idx) / max(1, total - 1))
                fecha = payload.ventana_inicio + timedelta(days=step)

            cosechas.append(
                CosechaEstanque(
                    estanque_id=pond_id,
                    cosecha_ola_id=ola.cosecha_ola_id,
                    status="p",
                    fecha_cosecha=fecha,
                    created_by=created_by_user_id
                )
            )

    if cosechas:
        db.add_all(cosechas)

    db.commit()
    db.refresh(ola)
    return ola
