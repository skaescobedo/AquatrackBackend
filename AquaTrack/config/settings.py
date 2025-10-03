from pydantic_settings import BaseSettings
from pydantic import field_validator

class Settings(BaseSettings):
    # App
    APP_NAME: str = "AquaTrack"
    API_PREFIX: str = "/api"

    # --- DB ---
    # Acepta DSN estilo: mysql+pymysql://user:pass@host:3306/db?charset=utf8mb4
    DATABASE_URL: str

    # --- JWT ---
    SECRET_KEY: str                 # igual que en tu .env base
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Otros ---
    PRODUCTION: bool = False
    UPLOAD_DIR: str = "uploads"
    CORS_ORIGINS: str | list[str] = "*"   # admite lista o string

    # Normaliza CORS_ORIGINS si viene como string con comas
    @field_validator("CORS_ORIGINS")
    @classmethod
    def _split_cors(cls, v):
        if isinstance(v, str) and v not in ("*", "") and "," in v:
            return [s.strip() for s in v.split(",")]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
