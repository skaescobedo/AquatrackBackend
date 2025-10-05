# utils/transactions.py
from contextlib import contextmanager
from sqlalchemy.orm import Session
from utils.db import SessionLocal

@contextmanager
def uow(session: Session | None = None):
    """
    Uso:
        with uow() as db:
            ... # operaciones
        # commit/rollback automático
    Si ya traes una sesión de get_db(), pásala para no abrir otra.
    """
    owns_session = session is None
    db = session or SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()
