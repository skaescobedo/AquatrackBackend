from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.user import Usuario
from models.cycle import Ciclo
from models.pond import Estanque
from models.biometria import Biometria, SOBFuente, SOBCambioLog
from models.seeding import SiembraEstanque, SiembraPlan
from schemas.biometria import BiometriaCreate, BiometriaUpdate

# Unificación de manejo temporal: TODO Mazatlán mediante utilidades centrales
from utils.datetime_utils import now_mazatlan, to_mazatlan_naive


class BiometriaService:
    """
    Servicio para gestión de biometrías.

    Lógica de SOB:
    1. Al sembrar: SOB base automática = 100%
    2. Primera biometría: Puede usar SOB 100% inicial o actualizarlo
    3. Biometrías posteriores: Solo actualizan si hay cambios reales
    4. Sin biometrías: Se usará SOB de proyección (futuro)
    """

    # ==========================================
    # HELPERS INTERNOS
    # ==========================================

    @staticmethod
    def _validate_cycle_and_pond(
            db: Session,
            ciclo_id: int,
            estanque_id: int
    ) -> tuple[Ciclo, Estanque]:
        ciclo = db.get(Ciclo, ciclo_id)
        if not ciclo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ciclo no encontrado")

        pond = db.get(Estanque, estanque_id)
        if not pond:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estanque no encontrado")

        if pond.granja_id != ciclo.granja_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El estanque no pertenece a la granja del ciclo"
            )
        return ciclo, pond

    @staticmethod
    def _validate_pond_has_seeding(
            db: Session,
            ciclo_id: int,
            estanque_id: int
    ) -> SiembraEstanque:
        siembra = (
            db.query(SiembraEstanque)
            .join(SiembraPlan)
            .filter(
                SiembraPlan.ciclo_id == ciclo_id,
                SiembraEstanque.estanque_id == estanque_id,
                SiembraEstanque.status == 'f'  # confirmada
            )
            .first()
        )
        if not siembra:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No hay siembra confirmada para este estanque en el ciclo. "
                       "Debe confirmar la siembra antes de registrar biometrías."
            )
        return siembra

    @staticmethod
    def _calculate_pp(n_muestra: int, peso_muestra_g: Decimal) -> Decimal:
        if n_muestra <= 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="n_muestra debe ser > 0")
        try:
            return (peso_muestra_g / Decimal(n_muestra)).quantize(Decimal("0.001"))
        except (InvalidOperation, ZeroDivisionError):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Error al calcular PP")

    @staticmethod
    def _calculate_increment(
            db: Session,
            ciclo_id: int,
            estanque_id: int,
            current_pp: Decimal
    ) -> Optional[Decimal]:
        last_bio = (
            db.query(Biometria)
            .filter(Biometria.ciclo_id == ciclo_id, Biometria.estanque_id == estanque_id)
            .order_by(desc(Biometria.fecha))
            .first()
        )
        if not last_bio:
            return None
        try:
            return (current_pp - Decimal(str(last_bio.pp_g))).quantize(Decimal("0.001"))
        except (InvalidOperation, TypeError):
            return None

    @staticmethod
    def _get_current_operational_sob(
            db: Session,
            ciclo_id: int,
            estanque_id: int
    ):
        """
        Obtiene el SOB operativo actual del estanque.

        Orden de búsqueda:
        1. Último cambio registrado en sob_cambio_log
        2. Última biometría que actualizó SOB
        3. SOB base por defecto = 100% (siembra inicial)
        """
        # 1) Último cambio registrado
        last_log = (
            db.query(SOBCambioLog)
            .filter(SOBCambioLog.ciclo_id == ciclo_id, SOBCambioLog.estanque_id == estanque_id)
            .order_by(desc(SOBCambioLog.changed_at))
            .first()
        )
        if last_log:
            return Decimal(str(last_log.sob_nueva_pct)), SOBFuente(last_log.fuente)

        # 2) Última biometría que actualizó SOB
        last_bio_sob = (
            db.query(Biometria)
            .filter(
                Biometria.ciclo_id == ciclo_id,
                Biometria.estanque_id == estanque_id,
                Biometria.actualiza_sob_operativa.is_(True)
            )
            .order_by(desc(Biometria.fecha))
            .first()
        )
        if last_bio_sob:
            fuente = SOBFuente(last_bio_sob.sob_fuente) if last_bio_sob.sob_fuente else SOBFuente.operativa_actual
            return Decimal(str(last_bio_sob.sob_usada_pct)), fuente

        # 3) SOB base por defecto (siembra = 100%)
        return Decimal("100.00"), SOBFuente.operativa_actual

    @staticmethod
    def _log_sob_change(
            db: Session,
            ciclo_id: int,
            estanque_id: int,
            sob_anterior: Optional[Decimal],
            sob_nueva: Decimal,
            fuente: SOBFuente,
            motivo: Optional[str],
            user_id: int
    ):
        log = SOBCambioLog(
            estanque_id=estanque_id,
            ciclo_id=ciclo_id,
            sob_anterior_pct=sob_anterior or Decimal("100.00"),
            sob_nueva_pct=sob_nueva,
            fuente=fuente.value,
            motivo=motivo or "Actualización desde biometría",
            changed_by=user_id
        )
        db.add(log)

    # ==========================================
    # COMANDOS PÚBLICOS
    # ==========================================

    @staticmethod
    def create(
            db: Session,
            ciclo_id: int,
            estanque_id: int,
            payload: BiometriaCreate,
            user_id: int
    ) -> Biometria:
        """
        Crea biometría fijando 'fecha' en el servidor en America/Mazatlan (naive).
        """
        # 1) Validaciones
        BiometriaService._validate_cycle_and_pond(db, ciclo_id, estanque_id)
        BiometriaService._validate_pond_has_seeding(db, ciclo_id, estanque_id)

        # 2) Cálculos
        try:
            peso_muestra = Decimal(str(payload.peso_muestra_g))
        except (InvalidOperation, ValueError):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="peso_muestra_g inválido")

        pp_g = BiometriaService._calculate_pp(payload.n_muestra, peso_muestra)
        incremento_g_sem = BiometriaService._calculate_increment(db, ciclo_id, estanque_id, pp_g)

        # 3) SOB operativo
        current_sob, current_source = BiometriaService._get_current_operational_sob(db, ciclo_id, estanque_id)
        actualiza_sob = False
        sob_fuente = current_source or SOBFuente.operativa_actual

        if payload.actualiza_sob_operativa:
            # Usuario quiere actualizar SOB
            try:
                new_sob = Decimal(str(payload.sob_usada_pct)).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="sob_usada_pct inválido")

            # Solo loguear si realmente cambia
            if current_sob is None or new_sob != current_sob:
                BiometriaService._log_sob_change(
                    db=db,
                    ciclo_id=ciclo_id,
                    estanque_id=estanque_id,
                    sob_anterior=current_sob,
                    sob_nueva=new_sob,
                    fuente=payload.sob_fuente,
                    motivo=payload.motivo_cambio_sob,
                    user_id=user_id
                )
                actualiza_sob = True
                sob_fuente = payload.sob_fuente
            sob_to_use = new_sob
        else:
            # Usar SOB operativo actual (puede ser 100% inicial)
            sob_to_use = current_sob

        # 4) Fecha de la muestra = ahora (America/Mazatlan) naive
        fecha_mzt = now_mazatlan()

        # 5) Persistir
        bio = Biometria(
            ciclo_id=ciclo_id,
            estanque_id=estanque_id,
            fecha=fecha_mzt,
            n_muestra=payload.n_muestra,
            peso_muestra_g=peso_muestra,
            pp_g=pp_g,
            sob_usada_pct=sob_to_use,
            incremento_g_sem=incremento_g_sem,
            notas=payload.notas,
            actualiza_sob_operativa=actualiza_sob,
            sob_fuente=sob_fuente.value if sob_fuente else None,
            created_by=user_id
        )
        db.add(bio)
        db.commit()
        db.refresh(bio)
        return bio

    @staticmethod
    def list_history_by_pond(
            db: Session,
            ciclo_id: int,
            estanque_id: int,
            fecha_desde: Optional[datetime] = None,
            fecha_hasta: Optional[datetime] = None,
            limit: int = 100,
            offset: int = 0
    ) -> List[Biometria]:
        """Historial de biometrías de un estanque."""
        query = db.query(Biometria).filter(
            Biometria.ciclo_id == ciclo_id,
            Biometria.estanque_id == estanque_id
        )

        if fecha_desde:
            query = query.filter(Biometria.fecha >= to_mazatlan_naive(fecha_desde))
        if fecha_hasta:
            query = query.filter(Biometria.fecha <= to_mazatlan_naive(fecha_hasta))

        return (
            query.order_by(desc(Biometria.fecha), desc(Biometria.created_at))
            .offset(offset).limit(limit).all()
        )

    @staticmethod
    def get_by_id(db: Session, biometria_id: int) -> Biometria:
        bio = db.get(Biometria, biometria_id)
        if not bio:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Biometría no encontrada")
        return bio

    @staticmethod
    def update(db: Session, biometria_id: int, payload: BiometriaUpdate) -> Biometria:
        bio = BiometriaService.get_by_id(db, biometria_id)
        if bio.actualiza_sob_operativa:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("No se puede editar una biometría que actualizó el SOB operativo. "
                        "Esta biometría está congelada para auditoría.")
            )
        if payload.notas is not None:
            bio.notas = payload.notas
        db.add(bio)
        db.commit()
        db.refresh(bio)
        return bio
