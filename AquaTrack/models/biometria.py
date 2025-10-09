from sqlalchemy import Column, BigInteger, Date, DateTime, Integer, Numeric, String, Enum, ForeignKey, Index
from sqlalchemy.sql import func
from utils.db import Base

class Biometria(Base):
    __tablename__ = "biometria"
    biometria_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ciclo_id = Column(BigInteger, ForeignKey("ciclo.ciclo_id"), nullable=False, index=True)
    estanque_id = Column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False, index=True)
    fecha = Column(Date, nullable=False)  # solo fecha; timestamp completo queda en created_at
    n_muestra = Column(Integer, nullable=False)
    peso_muestra_g = Column(Numeric(10,3), nullable=False)
    pp_g = Column(Numeric(7,3), nullable=False)
    sob_usada_pct = Column(Numeric(5,2), nullable=False)
    incremento_g_sem = Column(Numeric(7,3))
    notas = Column(String(255))
    actualiza_sob_operativa = Column(Integer, nullable=False, default=0)
    sob_fuente = Column(Enum('operativa_actual','ajuste_manual','reforecast', name='sob_fuente_enum'))
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

Index("ix_bio_estanque_fecha", Biometria.estanque_id, Biometria.fecha)
Index("ix_bio_ciclo_fecha", Biometria.ciclo_id, Biometria.fecha)
