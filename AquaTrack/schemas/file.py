# schemas/file.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import Field, conint, constr

from .shared import ORMModel
from .user import UsuarioMini
from .projection import ProyeccionMini
from .harvest import PlanCosechasMini
from .seeding import SiembraPlanRead  # o puedes definir un SiembraPlanMini si prefieres respuestas ligeras


# ============================================================
# Literales / constantes para "proposito"
# ============================================================

PropositoProyeccionLiteral = Literal["insumo_calculo", "respaldo", "reporte_publicado", "otro"]
PropositoPlanCosechasLiteral = Literal["plantilla", "respaldo", "otro"]
PropositoSiembraPlanLiteral = Literal["plantilla", "respaldo", "otro"]


# ============================================================
# Archivo
# ============================================================

class ArchivoBase(ORMModel):
    nombre_original: constr(strip_whitespace=True, min_length=1, max_length=200)
    tipo_mime: constr(strip_whitespace=True, min_length=1, max_length=120)
    tamanio_bytes: conint(ge=0)
    storage_path: constr(strip_whitespace=True, min_length=1, max_length=300)
    checksum: Optional[constr(strip_whitespace=True, max_length=64)] = None
    subido_por: Optional[int] = Field(default=None, description="Usuario que subió el archivo (opcional).")

class ArchivoCreate(ArchivoBase):
    pass

class ArchivoUpdate(ORMModel):
    nombre_original: Optional[constr(strip_whitespace=True, min_length=1, max_length=200)] = None
    tipo_mime: Optional[constr(strip_whitespace=True, min_length=1, max_length=120)] = None
    tamanio_bytes: Optional[conint(ge=0)] = None
    storage_path: Optional[constr(strip_whitespace=True, min_length=1, max_length=300)] = None
    checksum: Optional[constr(strip_whitespace=True, max_length=64)] = None
    subido_por: Optional[int] = None

class ArchivoMini(ORMModel):
    archivo_id: int
    nombre_original: str
    tipo_mime: str
    tamanio_bytes: int

class ArchivoRead(ArchivoBase):
    archivo_id: int
    created_at: datetime
    usuario: Optional[UsuarioMini] = None  # enriquecido si lo cargas


# ============================================================
# Archivo ↔ Proyeccion
# ============================================================

class ArchivoProyeccionBase(ORMModel):
    archivo_id: int
    proyeccion_id: int
    proposito: PropositoProyeccionLiteral = Field("otro")
    notas: Optional[constr(strip_whitespace=True, max_length=255)] = None

class ArchivoProyeccionCreate(ArchivoProyeccionBase):
    pass

class ArchivoProyeccionRead(ArchivoProyeccionBase):
    archivo_proyeccion_id: int
    linked_at: datetime

    # Enriquecimientos opcionales
    archivo: Optional[ArchivoMini] = None
    proyeccion: Optional[ProyeccionMini] = None


# ============================================================
# Archivo ↔ PlanCosechas
# ============================================================

class ArchivoPlanCosechasBase(ORMModel):
    archivo_id: int
    plan_cosechas_id: int
    proposito: PropositoPlanCosechasLiteral = Field("plantilla")
    notas: Optional[constr(strip_whitespace=True, max_length=255)] = None

class ArchivoPlanCosechasCreate(ArchivoPlanCosechasBase):
    pass

class ArchivoPlanCosechasRead(ArchivoPlanCosechasBase):
    archivo_plan_cosechas_id: int
    linked_at: datetime

    # Enriquecimientos opcionales
    archivo: Optional[ArchivoMini] = None
    plan: Optional[PlanCosechasMini] = None


# ============================================================
# Archivo ↔ SiembraPlan
# ============================================================

class ArchivoSiembraPlanBase(ORMModel):
    archivo_id: int
    siembra_plan_id: int
    proposito: PropositoSiembraPlanLiteral = Field("plantilla")
    notas: Optional[constr(strip_whitespace=True, max_length=255)] = None

class ArchivoSiembraPlanCreate(ArchivoSiembraPlanBase):
    pass

class ArchivoSiembraPlanRead(ArchivoSiembraPlanBase):
    archivo_siembra_plan_id: int
    linked_at: datetime

    # Enriquecimientos opcionales
    archivo: Optional[ArchivoMini] = None
    siembra_plan: Optional[SiembraPlanRead] = None  # o SiembraPlanMini si lo defines
