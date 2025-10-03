from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.security import decode_token
from models.user import Usuario

# En tu main incluirás este esquema en el OpenAPI (tokenUrl debe apuntar a tu /auth/login)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar el token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exc
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = db.get(Usuario, int(sub))
    if user is None:
        raise credentials_exc
    return user

async def get_current_active_user(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    # Ajusta si tu lógica de activo es distinta
    if current_user.estado != "a":
        raise HTTPException(status_code=400, detail="Usuario inactivo")
    return current_user
