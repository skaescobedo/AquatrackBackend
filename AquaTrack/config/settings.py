# config/settings.py
"""
Configuración centralizada de la aplicación usando Pydantic Settings.
Las variables se cargan desde el archivo .env
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Configuración de la aplicación"""

    # Base de datos
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ALLOW_ORIGINS: List[str] = ["http://localhost:4200"]

    # Gemini API (para proyecciones con IA)
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL_ID: str
    GEMINI_VISION_MODEL_ID: str
    GEMINI_TIMEOUT_MS: int = 120000  # 2 minutos

    # Proyecciones (límites de ingesta)
    MAX_PROJECTION_ROWS: int = 200  # Máximo de semanas permitidas
    PROJECTION_EXTRACTOR: str = "gemini"  # Solo gemini por ahora

    # Reforecast Automático
    REFORECAST_ENABLED: bool = True  # Master switch para todo el sistema
    REFORECAST_MIN_COVERAGE_PCT: float = 30.0  # % mínimo de estanques con datos
    REFORECAST_MIN_PONDS: int = 3  # Mínimo absoluto de estanques
    REFORECAST_WEEKEND_MODE: bool = False # True = Sáb-Dom, False = ventana libre
    REFORECAST_WINDOW_DAYS: int = 0  # Si weekend_mode=False, usar ±N días

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()