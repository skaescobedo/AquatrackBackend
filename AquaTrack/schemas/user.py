from pydantic import BaseModel, EmailStr, Field

class UserBase(BaseModel):
    username: str
    nombre: str
    apellido1: str
    apellido2: str | None = None
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(min_length=6)

class UserOut(UserBase):
    usuario_id: int
    is_admin_global: bool
    status: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginIn(BaseModel):
    username: str
    password: str
