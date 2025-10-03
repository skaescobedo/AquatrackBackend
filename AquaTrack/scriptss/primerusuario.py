# scriptss/primerusuario.py
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from utils.db import SessionLocal
from utils.security import hash_password
from models.user import Usuario

def create_initial_user():
    db = SessionLocal()
    try:
        existing = db.query(Usuario).filter(Usuario.username == "admin").first()
        if existing:
            print("⚠️ Usuario 'admin' ya existe (id:", existing.usuario_id, ").")
            return

        user = Usuario(
            username="admin",
            nombre="Administrador",
            apellido1="Sistema",
            apellido2="",
            email="admin@aquatrack.local",
            password_hash=hash_password("admin123"),
            estado="a",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print("✅ Usuario 'admin' creado. ID:", user.usuario_id)
    finally:
        db.close()

if __name__ == "__main__":
    create_initial_user()
