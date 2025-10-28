from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # MySQL: mysql+pymysql://user:pass@host:3306/dbname
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/aquatrack"
    SECRET_KEY: str = "CHANGE_ME"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12h
    ALGORITHM: str = "HS256"

    CORS_ALLOW_ORIGINS: List[str] = ["http://localhost:4200", "http://localhost:5173", "http://127.0.0.1:4200"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
