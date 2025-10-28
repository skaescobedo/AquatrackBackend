from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.security import oauth2_scheme, decode_access_token
from models.user import Usuario

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> Usuario:
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")
    user_id = int(payload["sub"])
    user = db.get(Usuario, user_id)
    if not user or user.status != "a":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado o inactivo")
    return user
