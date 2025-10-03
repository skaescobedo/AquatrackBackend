from pydantic import BaseModel, EmailStr, Field

# Lo que expones hacia afuera
class UserOut(BaseModel):
    usuario_id: int
    username: str
    nombre: str
    apellido1: str
    apellido2: str
    email: EmailStr
    estado: str

    class Config:
        from_attributes = True  # pydantic v2: permite model -> schema

# Para crear usuarios (si expones endpoint de registro/admin)
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    nombre: str
    apellido1: str
    apellido2: str
    email: EmailStr
    password: str = Field(min_length=8)

class UserUpdate(BaseModel):
    nombre: str | None = None
    apellido1: str | None = None
    apellido2: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    estado: str | None = None  # 'a'/'i'
