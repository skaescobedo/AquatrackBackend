# services/projection_service.py
"""
Servicio de gestión de proyecciones con auto-setup condicional de planes.
Adaptado a la estructura real del proyecto (sin PlanCosechas).

CAMBIOS IMPORTANTES:
- Sincroniza ciclo.fecha_inicio con primera fecha de proyección (solo V1)
- Ajusta ventana de siembras: [HOY, primera_fecha_proyección]
- Distribución uniforme de fechas mejorada (usa round en lugar de //)
"""

from datetime import datetime, date, timedelta
from typing import List, Tuple
from pathlib import Path
import tempfile
import os

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from models.projection import Proyeccion, ProyeccionLinea, SourceType
from models.cycle import Ciclo
from models.pond import Estanque
from models.seeding import SiembraPlan, SiembraEstanque
from models.harvest import CosechaOla, CosechaEstanque
from models.user import Usuario
from schemas.projection import ProyeccionUpdate, CanonicalProjection
from services.gemini_service import GeminiService, ExtractError
from utils.datetime_utils import now_mazatlan, today_mazatlan


# ===================================
# HELPERS
# ===================================

def _get_projection(db: Session, proyeccion_id: int) -> Proyeccion:
    """Obtiene una proyección o lanza error 404"""
    proj = db.get(Proyeccion, proyeccion_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Proyección no encontrada")
    return proj


def _validate_cycle_active(db: Session, ciclo_id: int) -> Ciclo:
    """Valida que el ciclo exista y esté activo"""
    cycle = db.get(Ciclo, ciclo_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    if cycle.status != 'a':
        raise HTTPException(status_code=400, detail="El ciclo no está activo")
    return cycle


def _check_version_unique(db: Session, ciclo_id: int, version: str, exclude_id: int | None = None):
    """Valida que no exista otra proyección con la misma versión"""
    query = db.query(Proyeccion).filter(
        and_(Proyeccion.ciclo_id == ciclo_id, Proyeccion.version == version)
    )
    if exclude_id:
        query = query.filter(Proyeccion.proyeccion_id != exclude_id)

    if query.first():
        raise HTTPException(status_code=409, detail=f"Ya existe una proyección con versión '{version}' en este ciclo")


def _check_no_draft_exists(db: Session, ciclo_id: int):
    """Valida que no exista un borrador pendiente"""
    draft = db.query(Proyeccion).filter(
        and_(Proyeccion.ciclo_id == ciclo_id, Proyeccion.status == 'b')
    ).first()

    if draft:
        raise HTTPException(status_code=409,
                            detail=f"Ya existe un borrador (versión '{draft.version}'). Publícalo o cancélalo antes de crear uno nuevo.")


def _next_version_for_cycle(db: Session, ciclo_id: int) -> str:
    """Genera el nombre de la siguiente versión"""
    cnt = db.query(func.count(Proyeccion.proyeccion_id)).filter(Proyeccion.ciclo_id == ciclo_id).scalar() or 0
    return f"V{cnt + 1}"


def _evenly_distribute_dates(start: date, end: date, n: int) -> List[date]:
    """
    Distribuye n fechas uniformemente entre start y end.

    MEJORADO: Usa round() en lugar de // para distribución más precisa.
    Compatible con la lógica de seeding_service.
    """
    if n <= 1:
        return [start]

    days = (end - start).days
    if days < 0:
        return [start]

    # Usar round para distribución más uniforme
    return [start + timedelta(days=round((days * i) / max(1, n - 1))) for i in range(n)]


# ===================================
# AUTO-SETUP CONDICIONAL
# ===================================

def _should_auto_setup(db: Session, ciclo_id: int) -> dict:
    """Determina si se debe hacer auto-setup"""
    result = {"should_setup_seeding": False, "should_setup_harvest": False, "reason": []}

    # Verificar siembra
    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo_id).first()
    if not plan:
        result["should_setup_seeding"] = True
        result["reason"].append("no_seeding_plan")
    else:
        if plan.status in ('e', 'f'):
            result["reason"].append(f"seeding_plan_in_progress_or_finished (status={plan.status})")
        else:
            result["should_setup_seeding"] = True
            result["reason"].append("seeding_plan_exists_but_planned (will_overwrite)")

    # Verificar cosecha
    olas = db.query(CosechaOla).filter(CosechaOla.ciclo_id == ciclo_id).all()
    if not olas:
        result["should_setup_harvest"] = True
        result["reason"].append("no_harvest_waves")
    else:
        in_progress = any(ola.status == 'r' for ola in olas)
        if in_progress:
            result["reason"].append("harvest_waves_in_progress")
        else:
            result["should_setup_harvest"] = True
            result["reason"].append("harvest_waves_exist_but_not_started (will_overwrite)")

    return result


def _auto_setup_seeding(
        db: Session,
        user: Usuario,
        ciclo: Ciclo,
        canonical: CanonicalProjection,
        primera_fecha_proyeccion: date
) -> dict:
    """
    Crea plan de siembras y siembras planeadas.

    CAMBIO IMPORTANTE:
    - ventana_inicio = HOY (fecha actual en Mazatlán)
    - ventana_fin = primera fecha de la proyección

    Si ventana_fin < ventana_inicio, se usa ventana_fin como inicio también.
    """
    stats = {"plan_created": False, "plan_updated": False, "ponds_created": 0}

    # NUEVO: Ventana de siembras ajustada
    hoy = today_mazatlan()
    ventana_inicio = hoy
    ventana_fin = primera_fecha_proyeccion

    # Validación: Si la proyección empieza antes de hoy, ajustar
    if ventana_fin < ventana_inicio:
        ventana_inicio = ventana_fin
        stats["warning"] = f"proyeccion_starts_before_today: ajustado ventana_inicio a {ventana_fin}"

    densidad = canonical.densidad_org_m2 if canonical.densidad_org_m2 is not None else 0.0
    talla = canonical.talla_inicial_g if canonical.talla_inicial_g is not None else 0.0

    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo.ciclo_id).first()

    if not plan:
        plan = SiembraPlan(
            ciclo_id=ciclo.ciclo_id,
            ventana_inicio=ventana_inicio,
            ventana_fin=ventana_fin,
            densidad_org_m2=densidad,
            talla_inicial_g=talla,
            status='p',
            observaciones="Auto-setup desde proyección",
            created_by=user.usuario_id,
        )
        db.add(plan)
        db.flush()
        stats["plan_created"] = True
    else:
        if plan.status == 'p':
            plan.ventana_inicio = ventana_inicio
            plan.ventana_fin = ventana_fin
            plan.densidad_org_m2 = densidad
            plan.talla_inicial_g = talla
            plan.observaciones = "Actualizado por auto-setup desde proyección"
            db.add(plan)
            stats["plan_updated"] = True

    ponds = (
        db.query(Estanque)
        .filter(Estanque.granja_id == ciclo.granja_id, Estanque.is_vigente == True)
        .order_by(Estanque.estanque_id.asc())
        .all()
    )

    if not ponds:
        db.commit()
        return stats

    # Eliminar siembras pendientes anteriores
    db.query(SiembraEstanque).filter(
        SiembraEstanque.siembra_plan_id == plan.siembra_plan_id,
        SiembraEstanque.status == 'p'
    ).delete(synchronize_session=False)

    # Distribuir fechas entre ventana_inicio y ventana_fin (usando función mejorada)
    dates = _evenly_distribute_dates(ventana_inicio, ventana_fin, len(ponds))
    bulk = []
    for p, d in zip(ponds, dates):
        bulk.append(
            SiembraEstanque(
                siembra_plan_id=plan.siembra_plan_id,
                estanque_id=p.estanque_id,
                status="p",
                fecha_tentativa=d,
                created_by=user.usuario_id,
            )
        )

    if bulk:
        db.bulk_save_objects(bulk)
        stats["ponds_created"] = len(bulk)

    db.commit()
    return stats


def _auto_setup_harvest(db: Session, user: Usuario, ciclo: Ciclo, canonical: CanonicalProjection) -> dict:
    """Crea olas de cosecha basadas en líneas con cosecha_flag"""
    stats = {"waves_created": 0, "ponds_created": 0}

    flagged_indices: List[int] = [i for i, ln in enumerate(canonical.lineas) if bool(ln.cosecha_flag)]

    ponds = (
        db.query(Estanque)
        .filter(Estanque.granja_id == ciclo.granja_id, Estanque.is_vigente == True)
        .order_by(Estanque.estanque_id.asc())
        .all()
    )

    if not flagged_indices:
        last = canonical.lineas[-1].fecha_plan
        ola = CosechaOla(
            ciclo_id=ciclo.ciclo_id,
            nombre="Ola Final (auto)",
            tipo="f",
            ventana_inicio=last,
            ventana_fin=last,
            status="p",
            orden=1,
            created_by=user.usuario_id,
        )
        db.add(ola)
        db.flush()
        stats["waves_created"] = 1

        if ponds:
            dates = _evenly_distribute_dates(ola.ventana_inicio, ola.ventana_fin, len(ponds))
            bulk = [
                CosechaEstanque(
                    estanque_id=p.estanque_id,
                    cosecha_ola_id=ola.cosecha_ola_id,
                    status="p",
                    fecha_cosecha=d,
                    created_by=user.usuario_id,
                )
                for p, d in zip(ponds, dates)
            ]
            if bulk:
                db.bulk_save_objects(bulk)
                stats["ponds_created"] += len(bulk)

        db.commit()
        return stats

    total_flags = len(flagged_indices)
    orden = 1

    for idx_pos, i in enumerate(flagged_indices):
        ln = canonical.lineas[i]
        start = canonical.lineas[i - 1].fecha_plan if i > 0 else ln.fecha_plan
        end = ln.fecha_plan
        objetivo = ln.retiro_org_m2 if ln.retiro_org_m2 is not None else None
        tipo = "f" if (idx_pos == total_flags - 1) else "p"
        nombre = f"Ola {orden} ({'final' if tipo == 'f' else 'parcial'})"

        ola = CosechaOla(
            ciclo_id=ciclo.ciclo_id,
            nombre=nombre,
            tipo=tipo,
            ventana_inicio=start,
            ventana_fin=end,
            objetivo_retiro_org_m2=objetivo,
            status="p",
            orden=orden,
            created_by=user.usuario_id,
        )
        db.add(ola)
        db.flush()
        stats["waves_created"] += 1
        orden += 1

        if ponds:
            dates = _evenly_distribute_dates(start, end, len(ponds))
            bulk = [
                CosechaEstanque(
                    estanque_id=p.estanque_id,
                    cosecha_ola_id=ola.cosecha_ola_id,
                    status="p",
                    fecha_cosecha=d,
                    created_by=user.usuario_id,
                )
                for p, d in zip(ponds, dates)
            ]
            if bulk:
                db.bulk_save_objects(bulk)
                stats["ponds_created"] += len(bulk)

    db.commit()
    return stats


# ===================================
# CREAR PROYECCIÓN DESDE ARCHIVO
# ===================================

async def create_projection_from_file(
        db: Session,
        ciclo_id: int,
        file: UploadFile,
        user_id: int,
        descripcion: str | None = None,
        version: str | None = None,
) -> Tuple[Proyeccion, List[str]]:
    """
    Crea proyección desde archivo con auto-setup condicional.

    CAMBIOS IMPORTANTES:
    - Si es V1, sincroniza ciclo.fecha_inicio con primera fecha de proyección
    - Ajusta ventana de siembras del auto-setup a [HOY, primera_fecha_proyección]
    """
    warnings: List[str] = []

    cycle = _validate_cycle_active(db, ciclo_id)
    _check_no_draft_exists(db, ciclo_id)

    # Guardar archivo temporalmente
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix)
    try:
        contents = await file.read()
        temp_file.write(contents)
        temp_file.close()

        # Extraer con Gemini
        gemini_service = GeminiService()
        try:
            canonical: CanonicalProjection = await gemini_service.extract_from_file(
                file_path=temp_file.name,
                file_name=file.filename,
                file_mime=file.content_type or "",
                ciclo_id=ciclo_id,
                granja_id=cycle.granja_id,
            )
        except ExtractError as e:
            if e.code in {"missing_required_columns", "type_error", "date_parse_error",
                          "empty_series", "limits_exceeded", "schema_validation_error", "invalid_json"}:
                detail = {"error": e.code}
                if e.missing:
                    detail["missing"] = e.missing
                if e.details:
                    detail["details"] = e.details
                raise HTTPException(status_code=422, detail=detail)
            elif e.code in {"unsupported_mime", "unsupported_media_type"}:
                raise HTTPException(status_code=415, detail=e.details or e.code)
            else:
                raise HTTPException(status_code=500, detail=f"gemini_extract_error: {e.code} {e.details or ''}".strip())
    finally:
        os.unlink(temp_file.name)
        await file.seek(0)

    final_version = version or _next_version_for_cycle(db, ciclo_id)
    _check_version_unique(db, ciclo_id, final_version)

    is_v1 = final_version.upper() == "V1"

    # NUEVO: Obtener primera fecha de proyección
    primera_fecha_proyeccion = canonical.lineas[0].fecha_plan if canonical.lineas else None

    # NUEVO: Si es V1, sincronizar fecha_inicio del ciclo
    if is_v1 and primera_fecha_proyeccion:
        fecha_anterior = cycle.fecha_inicio
        cycle.fecha_inicio = primera_fecha_proyeccion
        db.add(cycle)
        db.flush()

        if fecha_anterior != primera_fecha_proyeccion:
            warnings.append(
                f"sync_fecha_inicio: {fecha_anterior} → {primera_fecha_proyeccion}"
            )

    proy = Proyeccion(
        ciclo_id=ciclo_id,
        version=final_version.upper(),
        descripcion=descripcion or f"Proyección desde {file.filename}",
        status='p' if is_v1 else 'b',
        is_current=is_v1,
        published_at=now_mazatlan() if is_v1 else None,
        creada_por=user_id,
        source_type=SourceType.ARCHIVO,
        source_ref=file.filename,
        sob_final_objetivo_pct=canonical.sob_final_objetivo_pct,
        siembra_ventana_fin=canonical.siembra_ventana_fin,
    )
    db.add(proy)
    db.flush()

    bulk = [
        ProyeccionLinea(
            proyeccion_id=proy.proyeccion_id,
            edad_dias=ln.edad_dias,
            semana_idx=ln.semana_idx,
            fecha_plan=ln.fecha_plan,
            pp_g=ln.pp_g,
            incremento_g_sem=ln.incremento_g_sem,
            sob_pct_linea=ln.sob_pct_linea,
            cosecha_flag=ln.cosecha_flag,
            retiro_org_m2=ln.retiro_org_m2,
            nota=ln.nota,
        )
        for ln in canonical.lineas
    ]
    if bulk:
        db.bulk_save_objects(bulk)

    db.commit()
    db.refresh(proy)

    # Auto-setup condicional
    should_setup = _should_auto_setup(db, ciclo_id)

    if should_setup["should_setup_seeding"] and primera_fecha_proyeccion:
        user_obj = db.get(Usuario, user_id)
        seeding_stats = _auto_setup_seeding(
            db,
            user_obj,
            cycle,
            canonical,
            primera_fecha_proyeccion
        )

        if "warning" in seeding_stats:
            warnings.append(seeding_stats["warning"])

        if seeding_stats["plan_created"]:
            warnings.append(
                f"auto_setup_seeding: plan creado con {seeding_stats['ponds_created']} estanques "
                f"(ventana: {today_mazatlan()} → {primera_fecha_proyeccion})"
            )
        elif seeding_stats["plan_updated"]:
            warnings.append(
                f"auto_setup_seeding: plan actualizado con {seeding_stats['ponds_created']} estanques "
                f"(ventana: {today_mazatlan()} → {primera_fecha_proyeccion})"
            )

    if should_setup["should_setup_harvest"]:
        user_obj = db.get(Usuario, user_id)
        harvest_stats = _auto_setup_harvest(db, user_obj, cycle, canonical)
        warnings.append(
            f"auto_setup_harvest: {harvest_stats['waves_created']} olas creadas con {harvest_stats['ponds_created']} cosechas"
        )

    if not should_setup["should_setup_seeding"] and not should_setup["should_setup_harvest"]:
        warnings.append(f"no_auto_setup: {', '.join(should_setup['reason'])}")

    if is_v1:
        warnings.append("auto_published: V1 publicada automáticamente")

    return proy, warnings


# ===================================
# OPERACIONES CRUD
# ===================================

def list_projections(db: Session, ciclo_id: int, include_cancelled: bool = False) -> List[Proyeccion]:
    """Lista todas las proyecciones de un ciclo"""
    query = db.query(Proyeccion).filter(Proyeccion.ciclo_id == ciclo_id)
    if not include_cancelled:
        query = query.filter(Proyeccion.status != 'x')
    return query.order_by(desc(Proyeccion.created_at)).all()


def get_current_projection(db: Session, ciclo_id: int) -> Proyeccion | None:
    """Obtiene la proyección actual (is_current=True)"""
    return db.query(Proyeccion).filter(
        and_(Proyeccion.ciclo_id == ciclo_id, Proyeccion.is_current == True)
    ).first()


def get_draft_projection(db: Session, ciclo_id: int) -> Proyeccion | None:
    """Obtiene el borrador actual si existe"""
    return db.query(Proyeccion).filter(
        and_(Proyeccion.ciclo_id == ciclo_id, Proyeccion.status == 'b')
    ).first()


def get_projection_with_lines(db: Session, proyeccion_id: int) -> Proyeccion:
    """Obtiene una proyección con sus líneas"""
    proj = _get_projection(db, proyeccion_id)
    proj.lineas = sorted(proj.lineas, key=lambda x: x.semana_idx)
    return proj


def update_projection(db: Session, proyeccion_id: int, payload: ProyeccionUpdate) -> Proyeccion:
    """Actualiza metadatos (solo borradores)"""
    proj = _get_projection(db, proyeccion_id)

    if proj.status != 'b':
        raise HTTPException(status_code=400, detail="Solo se pueden editar proyecciones en borrador")

    if payload.descripcion is not None:
        proj.descripcion = payload.descripcion
    if payload.sob_final_objetivo_pct is not None:
        proj.sob_final_objetivo_pct = payload.sob_final_objetivo_pct
    if payload.siembra_ventana_fin is not None:
        proj.siembra_ventana_fin = payload.siembra_ventana_fin

    db.add(proj)
    db.commit()
    db.refresh(proj)

    return proj


def publish_projection(db: Session, proyeccion_id: int) -> Proyeccion:
    """Publica una proyección en borrador"""
    proj = _get_projection(db, proyeccion_id)

    if proj.status != 'b':
        raise HTTPException(status_code=400, detail="Solo se pueden publicar proyecciones en borrador")

    current = get_current_projection(db, proj.ciclo_id)
    if current:
        current.is_current = False
        db.add(current)

    proj.status = 'p'
    proj.is_current = True
    proj.published_at = now_mazatlan()

    db.add(proj)
    db.commit()
    db.refresh(proj)

    return proj


def cancel_projection(db: Session, proyeccion_id: int) -> Proyeccion:
    """Cancela una proyección"""
    proj = _get_projection(db, proyeccion_id)

    if proj.status == 'x':
        return proj

    if proj.is_current:
        raise HTTPException(status_code=400,
                            detail="No se puede cancelar la proyección actual. Publica otra versión primero.")

    proj.status = 'x'
    db.add(proj)
    db.commit()
    db.refresh(proj)

    return proj