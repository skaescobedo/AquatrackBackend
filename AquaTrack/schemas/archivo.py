from pydantic import BaseModel
from typing import Optional

class ArchivoOut(BaseModel):
    archivo_id: int
    nombre_original: str
    tipo_mime: str
    tamanio_bytes: int
    storage_path: str
    checksum: Optional[str] = None

class ArchivoVinculoIn(BaseModel):
    proposito: str = "otro"
    notas: Optional[str] = None

class ArchivoVinculoOut(BaseModel):
    archivo_proyeccion_id: int
    archivo_id: int
    proyeccion_id: int
    proposito: str
    notas: Optional[str] = None
