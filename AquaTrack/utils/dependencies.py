from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError
from utils.db import get_db
from utils.security import decode_token
from models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> Usuario:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    try:
        payload = decode_token(token)
        sub = payload.get("sub")
        if not sub:
            raise unauthorized
    except JWTError:
        raise unauthorized
    user = db.query(Usuario).filter(Usuario.username == sub).first()
    if not user or user.estado != "a":
        raise unauthorized
    return user
