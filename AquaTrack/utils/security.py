from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config.settings import settings
from models.user import Usuario

# --- Password hashing ---
# bcrypt_sha256 evita límite de 72 bytes de bcrypt puro
pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


# --- User helpers ---
def get_user_by_username(db: Session, username: str) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.email == email).first()

def authenticate_user(db: Session, username: str, password: str) -> Optional[Usuario]:
    # se permite login tanto con username como con email
    user = get_user_by_username(db, username) or get_user_by_email(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# --- JWT helpers ---
def _expire(minutes: int | None = None, days: int | None = None) -> datetime:
    now = datetime.now(timezone.utc)
    if minutes is not None:
        return now + timedelta(minutes=minutes)
    if days is not None:
        return now + timedelta(days=days)
    return now + timedelta(minutes=30)

def create_access_token(subject: str | int, extra_claims: dict | None = None) -> str:
    to_encode = {
        "sub": str(subject),
        "exp": _expire(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(subject: str | int, extra_claims: dict | None = None) -> str:
    to_encode = {
        "sub": str(subject),
        "exp": _expire(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    # Lanza JWTError si es inválido o expirado
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
