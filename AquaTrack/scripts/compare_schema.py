# Ejecuta desde la raíz del proyecto:
#   python -m scripts.seed_admin --username admin --email admin@example.com --password admin123 --nombre Admin --apellido1 Root
#
# Requiere que tu .env tenga DATABASE_URL y que tengas instalados:
#   pip install "passlib[bcrypt]" python-jose PyMySQL SQLAlchemy pydantic-settings

from argparse import ArgumentParser
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from utils.security import hash_password
from config.settings import settings
from models.usuario import Usuario

def upsert_admin(db: Session, *, username: str, email: str, password: str, nombre: str, apellido1: str, apellido2: str | None):
    user = (
        db.query(Usuario)
        .filter((Usuario.username == username) | (Usuario.email == email))
        .first()
    )

    if user:
        user.username = username
        user.email = email
        user.nombre = nombre
        user.apellido1 = apellido1
        user.apellido2 = apellido2
        user.password_hash = hash_password(password)
        user.estado = "a"
        user.is_admin_global = True
        db.commit()
        db.refresh(user)
        print(f"[OK] Admin actualizado: usuario_id={user.usuario_id}, username={user.username}, email={user.email}")
        return user

    user = Usuario(
        username=username,
        email=email,
        nombre=nombre,
        apellido1=apellido1,
        apellido2=apellido2,
        password_hash=hash_password(password),
        estado="a",
        is_admin_global=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"[OK] Admin creado: usuario_id={user.usuario_id}, username={user.username}, email={user.email}")
    return user

def main():
    ap = ArgumentParser()
    ap.add_argument("--username", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--apellido1", required=True)
    ap.add_argument("--apellido2", default=None)
    args = ap.parse_args()

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
    with Session(engine) as db:
        upsert_admin(
            db,
            username=args.username,
            email=args.email,
            password=args.password,
            nombre=args.nombre,
            apellido1=args.apellido1,
            apellido2=args.apellido2,
        )

if __name__ == "__main__":
    main()
