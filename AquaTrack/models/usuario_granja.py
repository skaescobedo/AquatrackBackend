from sqlalchemy import Column, BigInteger, CHAR, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from utils.db import Base

class UsuarioGranja(Base):
    __tablename__ = "usuario_granja"
    usuario_granja_id = Column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    granja_id = Column(BigInteger, ForeignKey("granja.granja_id"), nullable=False)
    rol_id = Column(BigInteger, ForeignKey("rol.rol_id"), nullable=False)
    estado = Column(CHAR(1), nullable=False, default="a")
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint("usuario_id", "granja_id", name="uq_usuario_granja"),
    )
