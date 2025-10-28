from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, BigInteger

from utils.db import Base

class Rol(Base):
    __tablename__ = "rol"

    rol_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255))
