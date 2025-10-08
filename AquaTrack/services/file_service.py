import hashlib
import os
from datetime import datetime
from typing import Tuple
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from config.settings import settings
from models.archivo import Archivo
from models.archivo_proyeccion import ArchivoProyeccion
from models.proyeccion import Proyeccion

ALLOWED_MIME = {"text/csv", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/pdf"}

def _ensure_upload_dir() -> str:
    base = settings.FILE_UPLOAD_DIR
    today = datetime.utcnow().strftime("%Y/%m")
    path = os.path.join(base, today)
    os.makedirs(path, exist_ok=True)
    return path

def _safe_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in (" ", ".", "_", "-")).strip()[:150]

def upload_file(db: Session, file: UploadFile, subido_por: int) -> Archivo:
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail="unsupported_media_type")
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    hasher = hashlib.sha256()
    total = 0
    tmp_dir = _ensure_upload_dir()
    safe_name = _safe_name(file.filename or "upload.bin")
    tmp_path = os.path.join(tmp_dir, f"tmp_{datetime.utcnow().timestamp()}_{safe_name}")

    with open(tmp_path, "wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                out.close()
                os.remove(tmp_path)
                raise HTTPException(status_code=413, detail="file_too_large")
            hasher.update(chunk)
            out.write(chunk)

    checksum = hasher.hexdigest()

    # Idempotencia por checksum
    existing = db.query(Archivo).filter(Archivo.checksum == checksum).first()
    if existing:
        # limpiar temporal si es duplicado
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return existing

    final_name = f"{checksum[:8]}_{safe_name}"
    final_path = os.path.join(tmp_dir, final_name)
    os.replace(tmp_path, final_path)

    arch = Archivo(
        nombre_original=safe_name,
        tipo_mime=file.content_type,
        tamanio_bytes=total,
        storage_path=final_path,
        checksum=checksum,
        subido_por=subido_por,
    )
    db.add(arch)
    db.commit()
    db.refresh(arch)
    return arch

def link_file_to_projection(db: Session, archivo_id: int, proyeccion_id: int, proposito: str, notas: str | None) -> ArchivoProyeccion:
    # Validaciones mínimas (existencia)
    arch = db.get(Archivo, archivo_id)
    if not arch:
        raise HTTPException(status_code=404, detail="archivo_not_found")
    proy = db.get(Proyeccion, proyeccion_id)
    if not proy:
        raise HTTPException(status_code=404, detail="proyeccion_not_found")

    ap = ArchivoProyeccion(
        archivo_id=archivo_id,
        proyeccion_id=proyeccion_id,
        proposito=proposito,
        notas=notas,
    )
    db.add(ap)
    db.commit()
    db.refresh(ap)
    return ap

def list_projection_files(db: Session, proyeccion_id: int) -> list[Tuple[ArchivoProyeccion, Archivo]]:
    from sqlalchemy import select
    stmt = (
        select(ArchivoProyeccion, Archivo)
        .join(Archivo, Archivo.archivo_id == ArchivoProyeccion.archivo_id)
        .where(ArchivoProyeccion.proyeccion_id == proyeccion_id)
        .order_by(ArchivoProyeccion.linked_at.desc())
    )
    return list(db.execute(stmt).all())
