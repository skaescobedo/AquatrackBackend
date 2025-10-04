from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class ArchivoProyeccionBase(BaseModel):
    archivo_id: int
    proyeccion_id: int
    proposito: str = Field(default="otro", pattern="^(insumo_calculo|respaldo|reporte_publicado|otro)$")
    notas: Optional[str]


class ArchivoProyeccionCreate(ArchivoProyeccionBase):
    pass


class ArchivoProyeccionOut(ArchivoProyeccionBase):
    archivo_proyeccion_id: int
    linked_at: datetime

    class Config:
        orm_mode = True
