from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class ArchivoBase(BaseModel):
    nombre_original: str = Field(..., max_length=255)
    ruta: str = Field(..., max_length=300)
    tipo_mime: Optional[str]
    archivo_tipo_id: Optional[int]
    subido_por: Optional[int]
    notas: Optional[str]


class ArchivoCreate(ArchivoBase):
    pass


class ArchivoOut(ArchivoBase):
    archivo_id: int
    peso_kb: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
