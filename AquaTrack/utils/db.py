# utils/db.py
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool  # pool por defecto en SQLAlchemy

from config.settings import settings


# ────────────────────────────────────────────────────────────────────────────────
# Engine (MySQL)
# - pool_pre_ping: valida conexiones antes de entregarlas (evita "MySQL server has gone away")
# - pool_recycle: renueva conexiones inactivas (ajusta según tu server/proveedor)
# - pool_size / max_overflow / pool_timeout: control del pool bajo carga
# - echo: logs SQL solo en modo debug (según settings.is_debug)
# ────────────────────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,          # ajusta según concurrencia esperada
    max_overflow=20,       # conexiones temporales extra cuando el pool está lleno
    pool_timeout=30,       # segundos esperando una conexión libre del pool
    pool_pre_ping=True,
    pool_recycle=1800,     # 30 min suele ir bien en MySQL gestionado
    echo=settings.is_debug,
    # Si tu URL no incluye charset, puedes añadirlo ahí: mysql+pymysql://.../db?charset=utf8mb4
)

# ────────────────────────────────────────────────────────────────────────────────
# Fábrica de sesiones
# - expire_on_commit=False: objetos siguen utilizables tras commit (útil al serializar)
# - autoflush=False: control explícito de cuándo se sincroniza con la BD
# ────────────────────────────────────────────────────────────────────────────────
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


# ────────────────────────────────────────────────────────────────────────────────
# Dependencia para FastAPI: una sesión por request
# - rollback ante excepción
# - cierre garantizado
# ────────────────────────────────────────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ────────────────────────────────────────────────────────────────────────────────
# Context manager para scripts/servicios (fuera de FastAPI)
# - hace commit si todo va bien; rollback si hay excepción
# ────────────────────────────────────────────────────────────────────────────────
@contextmanager
def session_scope() -> Generator[Session, None, None]:
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ────────────────────────────────────────────────────────────────────────────────
# Health check (útil para un endpoint /health o para startup)
# ────────────────────────────────────────────────────────────────────────────────
def ping() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
