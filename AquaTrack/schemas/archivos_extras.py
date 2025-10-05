from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field

from enums.enums import ArchivoPropositoProyeccionEnum
from .archivo import ArchivoOut

# --------------------------------------------------
#  RESPUESTA TRAS SUBIR ARCHIVO
# --------------------------------------------------
class ArchivoUploadResponse(BaseModel):
    archivo: ArchivoOut
    message: str = "Archivo subido correctamente"


# --------------------------------------------------
#  VINCULAR ARCHIVO A PROYECCIÓN
# --------------------------------------------------
class ArchivoProyeccionLinkIn(BaseModel):
    proyeccion_id: int
    proposito: ArchivoPropositoProyeccionEnum
    notas: Optional[str] = None


class ArchivoProyeccionLinkOut(BaseModel):
    archivo_proyeccion_id: int
    archivo_id: int
    proyeccion_id: int
    proposito: ArchivoPropositoProyeccionEnum  # <- antes era str
    notas: Optional[str] = None
    linked_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------
#  FILTRO Y PAGINACIÓN DE ARCHIVOS
#  (opcional: renombrar page_size -> per_page para alinear con common)
# --------------------------------------------------
class ArchivoFilter(BaseModel):
    q: Optional[str] = None
    mime: Optional[str] = None
    subido_por: Optional[int] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    page: int = 1
    page_size: int = 20  # o per_page: int = 20


class PageMeta(BaseModel):
    page: int
    page_size: int  # o per_page: int
    total: int


class ArchivoListResponse(BaseModel):
    data: List[ArchivoOut]
    meta: PageMeta


# --------------------------------------------------
#  IMPORTACIÓN Y PREVIEW DE ARCHIVO DE PROYECCIÓN
# --------------------------------------------------
class ProyeccionLineaPreview(BaseModel):
    semana_idx: int
    fecha_plan: Optional[date] = None           # <- era datetime
    edad_dias: Optional[int] = None
    pp_g: float
    sob_pct_linea: float
    incremento_g_sem: Optional[float] = None
    cosecha_flag: bool = False
    retiro_org_m2: Optional[float] = None
    rownum: int


class ValidationIssue(BaseModel):
    rownum: Optional[int] = None
    field: Optional[str] = None
    level: str = Field(..., pattern="^(error|warning|info)$")
    message: str


class ProyeccionImportPreview(BaseModel):
    archivo_id: int
    ciclo_id: Optional[int] = None
    version_sugerida: Optional[str] = None
    sob_final_objetivo_pct: Optional[float] = None
    lineas: List[ProyeccionLineaPreview]
    issues: List[ValidationIssue] = Field(default_factory=list)  # <- evita lista mutable


# --------------------------------------------------
#  ESTADO DE PROCESAMIENTO (ASYNC / VALIDACIÓN)
# --------------------------------------------------
class ArchivoProcessStatus(BaseModel):
    archivo_id: int
    status: str = Field(..., pattern="^(pending|processing|done|failed)$")
    progress_pct: Optional[float] = None
    message: Optional[str] = None
