from sqlalchemy import Column, BigInteger, Integer, Date, DECIMAL, String, ForeignKey
from sqlalchemy.orm import relationship
from utils.db import Base

class ProyeccionLinea(Base):
    __tablename__ = "proyeccion_linea"

    proyeccion_linea_id = Column(BigInteger, primary_key=True, autoincrement=True)
    proyeccion_id = Column(BigInteger, ForeignKey("proyeccion.proyeccion_id"), nullable=False)
    edad_dias = Column(Integer, nullable=False)
    semana_idx = Column(Integer, nullable=False)
    fecha_plan = Column(Date, nullable=False)
    pp_g = Column(DECIMAL(7,3), nullable=False)
    incremento_g_sem = Column(DECIMAL(7,3))
    sob_pct_linea = Column(DECIMAL(5,2), nullable=False)
    cosecha_flag = Column(Integer, nullable=False, default=0)  # tinyint(1)
    retiro_org_m2 = Column(DECIMAL(12,4))
    nota = Column(String(255))

    proyeccion = relationship("Proyeccion", back_populates="lineas")
