# schemas/archivo.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class ArchivoBase(BaseModel):
    nombre_original: str = Field(..., max_length=200)
    tipo_mime: str = Field(..., max_length=120)
    tamanio_bytes: int
    storage_path: str = Field(..., max_length=300)
    checksum: Optional[str] = Field(None, max_length=64)
    subido_por: Optional[int] = None

class ArchivoOut(ArchivoBase):
    archivo_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
