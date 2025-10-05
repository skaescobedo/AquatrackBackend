from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from schemas.common import Timestamps
from enums.enums import UsuarioEstadoEnum


class UsuarioGranjaBase(BaseModel):
    usuario_id: int
    granja_id: int
    estado: UsuarioEstadoEnum = UsuarioEstadoEnum.a


class UsuarioGranjaCreate(UsuarioGranjaBase):
    pass


class UsuarioGranjaUpdate(BaseModel):
    estado: Optional[UsuarioEstadoEnum] = None


class UsuarioGranjaOut(UsuarioGranjaBase, Timestamps):
    usuario_granja_id: int

    model_config = {"from_attributes": True}
