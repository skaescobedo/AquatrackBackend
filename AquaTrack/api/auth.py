from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from utils.db import get_db
from schemas.auth import TokenOut, MeOut
from services.auth_service import login as svc_login, get_profile
from utils.dependencies import get_current_user
from models.usuario import Usuario

router = APIRouter(prefix="/auth", tags=["auth"])

# IMPORTANTE: Swagger "Authorize" enviará form-urlencoded con grant_type=password
@router.post("/login", response_model=TokenOut)
def do_login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    token = svc_login(db, form.username, form.password)
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me", response_model=MeOut)
def me(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return get_profile(db, user)
