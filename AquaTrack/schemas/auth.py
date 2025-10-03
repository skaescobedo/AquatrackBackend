from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel):
    sub: str
    type: str

class LoginInput(BaseModel):
    username: str  # admite username o email
    password: str

class RefreshInput(BaseModel):
    refresh_token: str
