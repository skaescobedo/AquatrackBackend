# /services/projection_ingest_service.py
from __future__ import annotations
from datetime import datetime, timezone, date, timedelta
from typing import List, Tuple, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from config.settings import settings
from models.archivo import Archivo
from models.archivo_proyeccion import ArchivoProyeccion
from models.ciclo import Ciclo
from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from models.usuario import Usuario

# Auto-setup
from models.estanque import Estanque
from models.siembra_plan import SiembraPlan
from models.siembra_estanque import SiembraEstanque
from models.plan_cosechas import PlanCosechas
from models.cosecha_ola import CosechaOla
from models.cosecha_estanque import CosechaEstanque

from services.permissions_service import ensure_user_in_farm_or_admin, require_scopes

from services.extractors.base import ProjectionExtractor, ExtractError, CanonicalProjection
from services.extractors.gemini_extractor import GeminiExtractor
from services.projection_service import _autopublish_if_first


# --- selector de extractor (hoy fijo a gemini) ---
def _get_extractor() -> ProjectionExtractor:
    if settings.PROJECTION_EXTRACTOR.lower() != "gemini":
        # Por requerimiento escolar, forzamos gemini; si cambias .env, aquí podrías seleccionar otro proveedor.
        raise HTTPException(status_code=500, detail="projection_extractor_not_supported")
    try:
        return GeminiExtractor()
    except ExtractError as e:
        raise HTTPException(status_code=500, detail=f"gemini_init_error: {e.code} {e.details or ''}".strip())


def _next_version_for_cycle(db: Session, ciclo_id: int) -> str:
    cnt = db.query(func.count(Proyeccion.proyeccion_id)).filter(Proyeccion.ciclo_id == ciclo_id).scalar() or 0
    return f"v{cnt + 1}"


def _check_idempotency(db: Session, ciclo_id: int, checksum: str | None) -> Proyeccion | None:
    if not checksum:
        return None
    return (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id, Proyeccion.source_ref == checksum)
        .order_by(Proyeccion.created_at.desc())
        .first()
    )


# ---------------- helpers de fechas / distribución ----------------
def _evenly_distribute_dates(start: date, end: date, n: int) -> List[date]:
    if n <= 1:
        return [start]
    total_days = (end - start).days
    if total_days < 0:
        total_days = 0
    step = max(0, total_days // (n - 1))
    return [start + timedelta(days=step * i) for i in range(n)]


# ---------------- auto-setup inicial (siembra) ----------------
def _ensure_initial_seeding(db: Session, user: Usuario, ciclo: Ciclo, canonical: CanonicalProjection) -> dict:
    """
    Si no existe SiembraPlan para el ciclo:
      - Crea plan con:
          ventana_inicio = ciclo.fecha_inicio
          ventana_fin    = canonical.siembra_ventana_fin (o ciclo.fecha_fin_planificada o fecha_inicio)
          densidad_org_m2 = canonical.densidad_org_m2 (o 0)
          talla_inicial_g = canonical.talla_inicial_g (o 0)
      - Crea siembras planeadas (estado 'p') para TODOS los estanques de la granja,
        distribuyendo fechas entre ventana_inicio..ventana_fin.
    Si ya existe plan: no hace nada.
    """
    stats = {"plan_created": False, "ponds_created": 0}

    plan = db.query(SiembraPlan).filter(SiembraPlan.ciclo_id == ciclo.ciclo_id).first()
    if plan:
        return stats

    ventana_inicio = ciclo.fecha_inicio
    ventana_fin = canonical.siembra_ventana_fin or ciclo.fecha_fin_planificada or ciclo.fecha_inicio
    densidad = canonical.densidad_org_m2 if canonical.densidad_org_m2 is not None else 0.0
    talla = canonical.talla_inicial_g if canonical.talla_inicial_g is not None else 0.0

    plan = SiembraPlan(
        ciclo_id=ciclo.ciclo_id,
        ventana_inicio=ventana_inicio,
        ventana_fin=ventana_fin,
        densidad_org_m2=densidad,
        talla_inicial_g=talla,
        observaciones="Auto-setup desde proyección inicial",
        created_by=user.usuario_id,
    )
    db.add(plan)
    db.flush()

    ponds = (
        db.query(Estanque)
        .filter(Estanque.granja_id == ciclo.granja_id)
        .order_by(Estanque.estanque_id.asc())
        .all()
    )
    if not ponds:
        db.commit()
        stats["plan_created"] = True
        return stats

    dates = _evenly_distribute_dates(ventana_inicio, ventana_fin, len(ponds))
    bulk = []
    for p, d in zip(ponds, dates):
        bulk.append(
            SiembraEstanque(
                siembra_plan_id=plan.siembra_plan_id,
                estanque_id=p.estanque_id,
                estado="p",
                fecha_tentativa=d,
                created_by=user.usuario_id,
            )
        )
    if bulk:
        db.bulk_save_objects(bulk)
        stats["ponds_created"] = len(bulk)

    db.commit()
    stats["plan_created"] = True
    return stats


# ---------------- auto-setup inicial (cosecha) ----------------
def _ensure_initial_harvest(db: Session, user: Usuario, ciclo: Ciclo, canonical: CanonicalProjection) -> dict:
    """
    Si no existe PlanCosechas:
      - Crear plan.
      - Crear **una ola por cada línea** con `cosecha_flag = true`:
        * ventana_inicio = fecha_plan de la línea anterior (si existe; si no, misma fecha)
        * ventana_fin    = fecha_plan de la línea con flag
        * objetivo_retiro_org_m2 = retiro_org_m2 de esa línea (si viene)
        * tipo: 'p' para todas salvo la última detectada ('f')
      - Para cada ola, crear cosechas planeadas ('p') para todos los estanques,
        distribuyendo fechas entre ventana_inicio..ventana_fin.
    Si ya existe plan: no hace nada.
    """
    stats = {"plan_created": False, "waves_created": 0, "ponds_created": 0}

    plan = db.query(PlanCosechas).filter(PlanCosechas.ciclo_id == ciclo.ciclo_id).first()
    if plan:
        return stats

    plan = PlanCosechas(ciclo_id=ciclo.ciclo_id, nota_operativa="Auto-setup desde proyección inicial", created_by=user.usuario_id)
    db.add(plan)
    db.flush()

    # Detectar olas desde las líneas (orden ya viene del validador)
    flagged_indices: List[int] = [i for i, ln in enumerate(canonical.lineas) if bool(ln.cosecha_flag)]
    ponds = (
        db.query(Estanque)
        .filter(Estanque.granja_id == ciclo.granja_id)
        .order_by(Estanque.estanque_id.asc())
        .all()
    )

    if not flagged_indices:
        # fallback original: una ola final con la última fecha
        last = canonical.lineas[-1].fecha_plan
        ola = CosechaOla(
            plan_cosechas_id=plan.plan_cosechas_id,
            nombre="Ola Final (auto)",
            tipo="f",
            ventana_inicio=last,
            ventana_fin=last,
            estado="p",
            orden=1,
            created_by=user.usuario_id,
        )
        db.add(ola)
        db.flush()

        if ponds:
            dates = _evenly_distribute_dates(ola.ventana_inicio, ola.ventana_fin, len(ponds))
            bulk = []
            for p, d in zip(ponds, dates):
                bulk.append(
                    CosechaEstanque(
                        estanque_id=p.estanque_id,
                        cosecha_ola_id=ola.cosecha_ola_id,
                        estado="p",
                        fecha_cosecha=d,
                        created_by=user.usuario_id,
                    )
                )
            if bulk:
                db.bulk_save_objects(bulk)
                stats["ponds_created"] += len(bulk)

        db.commit()
        stats["plan_created"] = True
        stats["waves_created"] = 1
        return stats

    # Hay 1+ banderas de cosecha: una ola por cada bandera
    total_flags = len(flagged_indices)
    orden = 1
    for idx_pos, i in enumerate(flagged_indices):
        ln = canonical.lineas[i]
        start = canonical.lineas[i - 1].fecha_plan if i > 0 else ln.fecha_plan
        end = ln.fecha_plan
        objetivo = ln.retiro_org_m2 if ln.retiro_org_m2 is not None else None
        tipo = "f" if (idx_pos == total_flags - 1) else "p"
        nombre = f"Ola {orden} ({'final' if tipo=='f' else 'pre'})"

        ola = CosechaOla(
            plan_cosechas_id=plan.plan_cosechas_id,
            nombre=nombre,
            tipo=tipo,
            ventana_inicio=start,
            ventana_fin=end,
            objetivo_retiro_org_m2=objetivo,
            estado="p",
            orden=orden,
            created_by=user.usuario_id,
        )
        db.add(ola)
        db.flush()
        stats["waves_created"] += 1
        orden += 1

        if ponds:
            dates = _evenly_distribute_dates(start, end, len(ponds))
            bulk = []
            for p, d in zip(ponds, dates):
                bulk.append(
                    CosechaEstanque(
                        estanque_id=p.estanque_id,
                        cosecha_ola_id=ola.cosecha_ola_id,
                        estado="p",
                        fecha_cosecha=d,
                        created_by=user.usuario_id,
                    )
                )
            if bulk:
                db.bulk_save_objects(bulk)
                stats["ponds_created"] += len(bulk)

    db.commit()
    stats["plan_created"] = True
    return stats


def ingest_from_file(
    db: Session, user: Usuario, *, ciclo_id: int, archivo_id: int, force_reingest: bool
) -> Tuple[Proyeccion, List[str]]:
    # 1) validar ciclo y permisos
    ciclo = db.get(Ciclo, ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    ensure_user_in_farm_or_admin(db, user, ciclo.granja_id)
    require_scopes(db, user, ciclo.granja_id, {"projections:create"})

    # 2) validar archivo
    archivo = db.get(Archivo, archivo_id)
    if not archivo:
        raise HTTPException(status_code=404, detail="file_not_found")

    # 3) idempotencia por checksum+ciclo
    existing = _check_idempotency(db, ciclo_id, archivo.checksum)
    if existing and not force_reingest:
        raise HTTPException(status_code=409, detail=f"conflict_same_checksum: proyeccion_id={existing.proyeccion_id}")

    # 4) no permitir dos borradores simultáneos por ciclo (BD también valida)
    existing_draft = (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id, Proyeccion.status == "b")
        .first()
    )
    if existing_draft:
        raise HTTPException(status_code=409, detail="draft_projection_already_exists")

    # 5) extraer con Gemini
    extractor = _get_extractor()
    try:
        canonical: CanonicalProjection = extractor.extract(
            file_path=archivo.storage_path,
            file_name=archivo.nombre_original,
            file_mime=archivo.tipo_mime,
            ciclo_id=ciclo_id,
            granja_id=ciclo.granja_id,
        )
    except ExtractError as e:
        # Mapear a 422 o 415 según código
        if e.code in {"missing_required_columns", "type_error", "date_parse_error", "empty_series", "limits_exceeded", "schema_validation_error", "invalid_json"}:
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

    warnings: List[str] = []

    # 6) persistir proyección borrador
    version = _next_version_for_cycle(db, ciclo_id)
    proy = Proyeccion(
        ciclo_id=ciclo_id,
        version=version,
        descripcion="Borrador generado por IA desde archivo",
        status="b",
        is_current=False,
        creada_por=user.usuario_id,
        source_type="archivo",
        source_ref=archivo.checksum,
        # persistimos campos top-level derivados
        sob_final_objetivo_pct=str(canonical.sob_final_objetivo_pct) if canonical.sob_final_objetivo_pct is not None else None,
        siembra_ventana_fin=canonical.siembra_ventana_fin,
    )
    db.add(proy)
    db.flush()  # obtiene proyeccion_id

    # 7) insertar líneas
    bulk = []
    for ln in canonical.lineas:
        bulk.append(
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
        )
    if bulk:
        db.bulk_save_objects(bulk)

    # 8) vincular archivo a proyección
    db.add(ArchivoProyeccion(
        archivo_id=archivo_id,
        proyeccion_id=proy.proyeccion_id,
        proposito="insumo_calculo",
        notas="Archivo fuente normalizado por IA",
    ))

    # 9) Auto-setup inicial (si no existen planes)
    seeding_stats = _ensure_initial_seeding(db, user, ciclo, canonical)
    harvest_stats = _ensure_initial_harvest(db, user, ciclo, canonical)
    if seeding_stats["plan_created"] or harvest_stats["plan_created"]:
        warnings.append("auto_setup: se crearon planes iniciales de siembra/cosecha desde la proyección.")

    db.commit()
    db.refresh(proy)

    # Autopublish si es la primera del ciclo
    if _autopublish_if_first(db, proy):
        warnings.append("auto_published=True (first_projection_in_cycle)")
    else:
        warnings.append("auto_published=False (current_projection_already_exists)")
    return proy, warnings
