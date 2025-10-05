# scripts/compare_schema.py
import os
import sys
from pathlib import Path

# === Bootstrap de rutas: agrega el root del proyecto (AquaTrack) al sys.path ===
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from typing import Optional, Tuple, Dict
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.sql.schema import Table, Column
from sqlalchemy.sql.sqltypes import Enum, String, Numeric
from sqlalchemy.orm import DeclarativeMeta

# Importa tu Base y TODOS los modelos para registrar metadata
from utils.db import Base
from models.archivo import Archivo
from models.archivo_proyeccion import ArchivoProyeccion
from models.biometria import Biometria
from models.ciclo import Ciclo
from models.ciclo_resumen import CicloResumen
from models.cosecha_estanque import CosechaEstanque
from models.cosecha_fecha_log import CosechaFechaLog
from models.cosecha_ola import CosechaOla
from models.estanque import Estanque
from models.granja import Granja
from models.password_reset_token import PasswordResetToken
from models.plan_cosechas import PlanCosechas
from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from models.rol import Rol
from models.siembra_estanque import SiembraEstanque
from models.siembra_fecha_log import SiembraFechaLog
from models.siembra_plan import SiembraPlan
from models.sob_cambio_log import SobCambioLog
from models.usuario import Usuario
from models.usuario_granja import UsuarioGranja
from models.usuario_rol import UsuarioRol

def type_signature(coltype) -> Tuple[str, Optional[int], Optional[Tuple[int, int]]]:
    name = coltype.__class__.__name__
    length = getattr(coltype, "length", None)
    precision = getattr(coltype, "precision", None)
    scale = getattr(coltype, "scale", None)
    if isinstance(coltype, Numeric):
        return (name, None, (precision, scale))
    return (name, length, None)

def get_enum_values(coltype) -> Optional[Tuple[str, Tuple[str, ...]]]:
    if isinstance(coltype, Enum):
        enum_vals = tuple(getattr(coltype, "enums", []) or [])
        enum_name = getattr(coltype, "name", None) or coltype.__class__.__name__
        return (enum_name, enum_vals)
    return None

def normalize_default(d):
    if d is None:
        return None
    return str(d).strip().lower()

def compare_table(insp: Inspector, table: Table):
    tname = table.name
    print(f"\n=== Tabla: {tname} ===")
    db_cols = {c["name"]: c for c in insp.get_columns(tname)}
    db_pks = insp.get_pk_constraint(tname).get("constrained_columns", []) or []
    db_uniques = insp.get_unique_constraints(tname) or []
    db_unique_cols = set()
    for uq in db_uniques:
        cols = tuple(uq.get("column_names") or [])
        if len(cols) == 1:
            db_unique_cols.add(cols[0])

    orm_cols: Dict[str, Column] = {c.name: c for c in table.columns}

    for cname, orm_col in orm_cols.items():
        if cname not in db_cols:
            print(f"  [FALTA EN BD] Columna en ORM pero no en BD: {cname}")
            continue

        db_col = db_cols[cname]

        orm_nullable = orm_col.nullable
        db_nullable = db_col.get("nullable", True)
        if orm_nullable != db_nullable:
            print(f"  [NULLABLE] {cname}: ORM={orm_nullable} vs BD={db_nullable}")

        orm_sig = type_signature(orm_col.type)
        db_sig = type_signature(db_col.get("type"))
        if orm_sig != db_sig:
            print(f"  [TIPO] {cname}: ORM={orm_sig} vs BD={db_sig}")

        orm_enum = get_enum_values(orm_col.type)
        db_enum = get_enum_values(db_col.get("type"))
        if orm_enum or db_enum:
            if orm_enum != db_enum:
                print(f"  [ENUM] {cname}: ORM={orm_enum} vs BD={db_enum}")

        orm_def = normalize_default(getattr(orm_col.server_default, "arg", None))
        db_def = normalize_default(db_col.get("default"))
        if orm_def != db_def:
            print(f"  [DEFAULT] {cname}: ORM={orm_def} vs BD={db_def}")

        orm_pk = orm_col.primary_key
        db_pk = cname in db_pks
        if orm_pk != db_pk:
            print(f"  [PK] {cname}: ORM={orm_pk} vs BD={db_pk}")

        orm_unique = orm_col.unique or False
        db_unique_simple = cname in db_unique_cols
        if orm_unique != db_unique_simple:
            print(f"  [UNIQUE] {cname}: ORM={orm_unique} vs BD={db_unique_simple}")

    for cname in db_cols:
        if cname not in orm_cols:
            print(f"  [FALTA EN ORM] Columna en BD pero no en ORM: {cname}")

    checks = insp.get_check_constraints(tname) or []
    if checks:
        print(f"  Checks BD: {[c.get('name') for c in checks]}")
    indexes = insp.get_indexes(tname) or []
    if indexes:
        print(f"  Índices BD: {[i.get('name') for i in indexes]}")

def main():
    dburl = os.environ.get("DATABASE_URL")
    if not dburl:
        raise SystemExit("ERROR: Exporta DATABASE_URL (mysql+pymysql://user:pass@host:3306/db)")

    engine = create_engine(dburl)
    insp = inspect(engine)

    db_tables = set(insp.get_table_names())
    for tname, table in Base.metadata.tables.items():
        if tname not in db_tables:
            print(f"\n=== Tabla: {tname} ===")
            print("  [FALTA EN BD] La tabla no existe en la base de datos.")
            continue
        compare_table(insp, table)

if __name__ == "__main__":
    main()
