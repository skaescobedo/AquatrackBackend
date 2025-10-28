from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from utils.db import get_db
from utils.dependencies import get_current_user
from schemas.user import Token, UserCreate, UserOut
from services.auth_service import authenticate_user, issue_access_token, create_user
from models.user import Usuario

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm entrega username/password via form-urlencoded
    user = authenticate_user(db, form_data.username, form_data.password)
    token = issue_access_token(user)
    return {"access_token": token, "token_type": "bearer"}

@router.post("/register", response_model=UserOut)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    user = create_user(db, payload)
    return user

@router.get("/me", response_model=UserOut)
def me(user: Usuario = Depends(get_current_user)):
    return user
