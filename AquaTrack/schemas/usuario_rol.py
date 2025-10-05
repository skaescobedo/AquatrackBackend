from pydantic import BaseModel


class UsuarioRolBase(BaseModel):
    usuario_id: int
    rol_id: int


class UsuarioRolCreate(UsuarioRolBase):
    pass


class UsuarioRolOut(UsuarioRolBase):
    model_config = {"from_attributes": True}
