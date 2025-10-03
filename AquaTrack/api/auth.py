from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError

from utils.db import get_db
from utils.security import authenticate_user, create_access_token, create_refresh_token, decode_token
from utils.dependencies import get_current_active_user
from schemas.auth import Token, RefreshInput
from schemas.user import UserOut
from models.user import Usuario

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Swagger/Authorize mandará username y password como form-data
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    access = create_access_token(user.usuario_id)
    refresh = create_refresh_token(user.usuario_id)
    return Token(access_token=access, refresh_token=refresh)

@router.post("/refresh", response_model=Token)
def refresh_token(data: RefreshInput):
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token inválido")
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Token inválido")
        return Token(
            access_token=create_access_token(sub),
            refresh_token=create_refresh_token(sub),
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

@router.get("/me", response_model=UserOut)
def me(current_user: Usuario = Depends(get_current_active_user)):
    return current_user
