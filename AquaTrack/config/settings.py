# config/settings.py
from __future__ import annotations

from pathlib import Path
from datetime import timedelta
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, FieldValidationInfo


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,   # Permite production/PRODUCTION/Production
        extra="ignore",         # Ignora variables extra en el .env si las hubiera
    )

    # ───────────────────────────────
    # Base de datos
    # ───────────────────────────────
    DATABASE_URL: str  # p.ej. mysql+pymysql://user:pass@localhost/aquatrack

    # ───────────────────────────────
    # Seguridad / JWT
    # ───────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ───────────────────────────────
    # Entorno
    # ───────────────────────────────
    PRODUCTION: bool = False

    # ───────────────────────────────
    # Archivos
    # ───────────────────────────────
    UPLOAD_DIR: Path | str = "uploads"

    # (Opcional) CORS
    CORS_ORIGINS: List[str] = []

    # ───────────────────────────────
    # Validators / Normalizadores
    # ───────────────────────────────
    @field_validator("ALGORITHM")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        allowed = {"HS256", "HS384", "HS512"}
        if v not in allowed:
            raise ValueError(f"ALGORITHM debe ser uno de {allowed}")
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info: FieldValidationInfo) -> str:
        # Reglas mínimas: longitud y no solo espacios
        if not v or len(v.strip()) < 16:
            mode = "producción" if info.data.get("PRODUCTION") else "desarrollo"
            raise ValueError(f"SECRET_KEY demasiado corta para {mode}. Usa ≥16 caracteres.")
        return v

    @field_validator("UPLOAD_DIR", mode="before")
    @classmethod
    def normalize_upload_dir(cls, v):
        # Permite str o Path; no obliga a que exista en este momento
        return Path(v) if isinstance(v, str) else v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors(cls, v):
        # Permite definir en .env como: http://localhost:5173,http://localhost:3000
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    # ───────────────────────────────
    # Helpers / Props
    # ───────────────────────────────
    @property
    def is_debug(self) -> bool:
        return not self.PRODUCTION

    @property
    def upload_path(self) -> Path:
        # No falla si no existe; puedes crearla en el startup de FastAPI
        return Path(self.UPLOAD_DIR).resolve()

    @property
    def access_token_timedelta(self) -> timedelta:
        return timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)

    @property
    def refresh_token_timedelta(self) -> timedelta:
        return timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)


settings = Settings()
