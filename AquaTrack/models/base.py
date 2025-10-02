# models/base.py
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy import MetaData

# ───────────────────────────────────────────────
# Convención de nombres para constraints / índices
# Esto mantiene consistencia en nombres de PK, FK, índices, etc.
# ───────────────────────────────────────────────
convention = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


# ───────────────────────────────────────────────
# Clase base de la que heredarán todos los modelos
# ───────────────────────────────────────────────
class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos ORM."""
    metadata = metadata

    # Si no defines __tablename__ en el modelo,
    # lo genera automáticamente en minúsculas con el nombre de la clase
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
