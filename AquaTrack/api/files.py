from fastapi import APIRouter, Depends, UploadFile, File, Path
from sqlalchemy.orm import Session
from utils.db import get_db
from utils.dependencies import get_current_user
from models.usuario import Usuario
from services.file_service import upload_file, link_file_to_projection, list_projection_files
from schemas.archivo import ArchivoOut, ArchivoVinculoIn, ArchivoVinculoOut

router = APIRouter(prefix="/files", tags=["files"])

@router.post("", response_model=ArchivoOut)
def upload(file: UploadFile = File(...), db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    arch = upload_file(db, file, user.usuario_id)
    return {
        "archivo_id": arch.archivo_id,
        "nombre_original": arch.nombre_original,
        "tipo_mime": arch.tipo_mime,
        "tamanio_bytes": arch.tamanio_bytes,
        "storage_path": arch.storage_path,
        "checksum": arch.checksum,
    }

@router.post("/projections/{proyeccion_id}/{archivo_id}", response_model=ArchivoVinculoOut)
def link(
    proyeccion_id: int = Path(..., gt=0),
    archivo_id: int = Path(..., gt=0),
    body: ArchivoVinculoIn = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ap = link_file_to_projection(db, archivo_id, proyeccion_id, body.proposito if body else "otro", body.notas if body else None)
    return {
        "archivo_proyeccion_id": ap.archivo_proyeccion_id,
        "archivo_id": ap.archivo_id,
        "proyeccion_id": ap.proyeccion_id,
        "proposito": ap.proposito,
        "notas": ap.notas,
    }

@router.get("/projections/{proyeccion_id}", response_model=list[ArchivoOut])
def list_for_projection(proyeccion_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    rows = list_projection_files(db, proyeccion_id)
    result = []
    for _, a in rows:
        result.append({
            "archivo_id": a.archivo_id,
            "nombre_original": a.nombre_original,
            "tipo_mime": a.tipo_mime,
            "tamanio_bytes": a.tamanio_bytes,
            "storage_path": a.storage_path,
            "checksum": a.checksum,
        })
    return result
