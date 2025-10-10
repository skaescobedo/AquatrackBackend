# /services/projection_ingest_service.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from config.settings import settings
from models.archivo import Archivo
from models.archivo_proyeccion import ArchivoProyeccion
from models.ciclo import Ciclo
from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from models.usuario import Usuario
from services.permissions_service import ensure_user_in_farm_or_admin, require_scopes

from services.extractors.base import ProjectionExtractor, ExtractError, CanonicalProjection
from services.extractors.gemini_extractor import GeminiExtractor

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
        elif e.code in {"unsupported_media_type"}:
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
        # >>> NUEVO: persistimos los campos derivados o devueltos por el modelo
        sob_final_objetivo_pct=canonical.sob_final_objetivo_pct,
        siembra_ventana_inicio=canonical.siembra_ventana_inicio,
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
        # Warning si sob fue clamped por modelo base (no tenemos flag directo; omitimos)
    if bulk:
        db.bulk_save_objects(bulk)

    # 8) vincular archivo a proyección
    db.add(ArchivoProyeccion(
        archivo_id=archivo_id,
        proyeccion_id=proy.proyeccion_id,
        proposito="insumo_calculo",
        notas="Archivo fuente normalizado por IA",
    ))

    db.commit()
    db.refresh(proy)
    return proy, warnings
