# /config/settings.py
from __future__ import annotations
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # raíz del proyecto

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    DEFAULT_TZ: str = "America/Mazatlan"  # Mochis
    DB_TZ: str = "America/Mazatlan"  # cómo están guardados los naive de la BD

    # Core
    DATABASE_URL: str = Field(...)
    JWT_SECRET: str = Field(...)
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = "http://localhost:4200"

    # Archivos
    FILE_UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 50

    # Entorno
    ENV: str = "dev"

    # Ingesta de proyección (IA)
    PROJECTION_EXTRACTOR: str = "gemini"
    GEMINI_API_KEY: str | None = None

    # IMPORTANTE: defaults ya con prefijo "models/" para google-genai v1
    GEMINI_MODEL_ID: str = "models/gemini-1.5-flash"
    GEMINI_VISION_MODEL_ID: str = "models/gemini-1.5-pro"
    GEMINI_TIMEOUT_MS: int = 150_000

    # Límites de ingesta
    MAX_PROJECTION_ROWS: int = 1000

settings = Settings()
