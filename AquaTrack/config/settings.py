# config/settings.py
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # carpeta raíz del proyecto

class Settings(BaseSettings):
    # v2: usa model_config en vez de class Config
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        # env_prefix="AQUA_",  # opcional si quisieras prefijos en .env
    )

    DATABASE_URL: str = Field(...)
    JWT_SECRET: str = Field(...)
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = "http://localhost:4200"
    FILE_UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 50
    ENV: str = "dev"
    GEMINI_API_KEY: str | None = None  # opcional en S2 (parser local)

settings = Settings()
