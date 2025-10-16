#models/proyeccion_linea
from sqlalchemy import Column, BigInteger, Integer, Date, String, Numeric, Boolean, ForeignKey, Index
from utils.db import Base

class ProyeccionLinea(Base):
    __tablename__ = "proyeccion_linea"
    proyeccion_linea_id = Column(BigInteger, primary_key=True, autoincrement=True)
    proyeccion_id = Column(BigInteger, ForeignKey("proyeccion.proyeccion_id"), nullable=False, index=True)
    edad_dias = Column(Integer, nullable=False)
    semana_idx = Column(Integer, nullable=False)
    fecha_plan = Column(Date, nullable=False)
    pp_g = Column(Numeric(7, 3), nullable=False)
    incremento_g_sem = Column(Numeric(7, 3))
    sob_pct_linea = Column(Numeric(5, 2), nullable=False)
    cosecha_flag = Column(Boolean, nullable=False, default=False)
    retiro_org_m2 = Column(Numeric(12, 4))
    nota = Column(String(255))

Index("ix_pl_proy_semana", ProyeccionLinea.proyeccion_id, ProyeccionLinea.semana_idx)
Index("ix_pl_proy_fecha", ProyeccionLinea.proyeccion_id, ProyeccionLinea.fecha_plan)
