from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enums.enums import ArchivoPropositoProyeccionEnum


class ArchivoProyeccionBase(BaseModel):
    archivo_id: int
    proyeccion_id: int
    proposito: ArchivoPropositoProyeccionEnum = ArchivoPropositoProyeccionEnum.otro
    notas: Optional[str] = Field(None, max_length=255)


class ArchivoProyeccionCreate(ArchivoProyeccionBase):
    pass


class ArchivoProyeccionOut(ArchivoProyeccionBase):
    archivo_proyeccion_id: int
    linked_at: datetime

    model_config = {"from_attributes": True}
