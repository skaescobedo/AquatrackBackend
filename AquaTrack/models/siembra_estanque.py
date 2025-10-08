from sqlalchemy import Column, BigInteger, Date, DateTime, Numeric, String, CHAR, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from utils.db import Base

class SiembraEstanque(Base):
    __tablename__ = "siembra_estanque"
    siembra_estanque_id = Column(BigInteger, primary_key=True, autoincrement=True)
    siembra_plan_id = Column(BigInteger, ForeignKey("siembra_plan.siembra_plan_id"), nullable=False, index=True)
    estanque_id = Column(BigInteger, ForeignKey("estanque.estanque_id"), nullable=False, index=True)
    estado = Column(CHAR(1), nullable=False, default="p")  # p=planeado, f=finalizado
    fecha_tentativa = Column(Date)
    fecha_siembra = Column(Date)
    lote = Column(String(80))
    densidad_override_org_m2 = Column(Numeric(12,4))
    talla_inicial_override_g = Column(Numeric(7,3))
    created_by = Column(BigInteger, ForeignKey("usuario.usuario_id"))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    observaciones = Column(String(150))

    __table_args__ = (UniqueConstraint("siembra_plan_id", "estanque_id", name="uq_siembra_unica_por_estanque_en_plan"),)

Index("ix_se_plan_estado", SiembraEstanque.siembra_plan_id, SiembraEstanque.estado)
Index("ix_se_plan_fecha_tentativa", SiembraEstanque.siembra_plan_id, SiembraEstanque.fecha_tentativa)
Index("ix_se_plan_fecha_siembra", SiembraEstanque.siembra_plan_id, SiembraEstanque.fecha_siembra)
Index("ix_se_plan_created", SiembraEstanque.siembra_plan_id, SiembraEstanque.created_at)
