# config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "AquaTrack"
    API_PREFIX: str = "/api"
    PRODUCTION: bool = False

    # --- DB ---
    # DSN estilo: mysql+pymysql://user:pass@host:3306/db?charset=utf8mb4
    DATABASE_URL: str

    # --- JWT ---
    SECRET_KEY: str                  # igual que en tu .env base
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Uploads ---
    UPLOAD_DIR: str = "uploads"

    # --- CORS ---
    # Acepta lista o string (p.ej. "https://a.com,https://b.com" o "*")
    CORS_ORIGINS: str | list[str] = "*"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v):
        # Si viene como string con comas, lo convertimos a lista.
        # Si viene como "*" o "", lo dejamos tal cual (FastAPI lo interpreta).
        if isinstance(v, str):
            s = v.strip()
            if s and s != "*" and "," in s:
                return [p.strip() for p in s.split(",") if p.strip()]
            return s or "*"
        return v

    PROYECCION_HOOKS_ENABLED: bool = True
    PROYECCION_AUTO_CREATE_ON_MUTATIONS: bool = True
    PROYECCION_CLONE_FROM_CURRENT_ON_MUTATIONS: bool = True
    PROYECCION_BOOTSTRAP_ON_PLAN_CREATE: bool = True
    PROYECCION_BOOTSTRAP_DELTA_G_SEM: float = 1.0
    PROYECCION_BOOTSTRAP_WEEKS: int = 16
    PROYECCION_REQUIRE_PUBLICADA: bool = False
    PROYECCION_STRICT_FAIL: bool = False
    PROYECCION_EMIT_HEADERS: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_nested_delimiter="__",
    )

settings = Settings()
