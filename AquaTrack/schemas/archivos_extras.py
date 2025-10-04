from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
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
    proposito: str = Field(..., pattern="^(insumo_calculo|respaldo|reporte_publicado|otro)$")
    notas: Optional[str] = None


class ArchivoProyeccionLinkOut(BaseModel):
    archivo_proyeccion_id: int
    archivo_id: int
    proyeccion_id: int
    proposito: str
    notas: Optional[str] = None
    linked_at: datetime

    class Config:
        from_attributes = True


# --------------------------------------------------
#  FILTRO Y PAGINACIÓN DE ARCHIVOS
# --------------------------------------------------
class ArchivoFilter(BaseModel):
    q: Optional[str] = None             # búsqueda por nombre_original
    mime: Optional[str] = None
    subido_por: Optional[int] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    page: int = 1
    page_size: int = 20


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class ArchivoListResponse(BaseModel):
    data: List[ArchivoOut]
    meta: PageMeta


# --------------------------------------------------
#  IMPORTACIÓN Y PREVIEW DE ARCHIVO DE PROYECCIÓN
# --------------------------------------------------
class ProyeccionLineaPreview(BaseModel):
    semana_idx: int
    fecha_plan: Optional[datetime] = None
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
    issues: List[ValidationIssue] = []


# --------------------------------------------------
#  ESTADO DE PROCESAMIENTO (ASYNC / VALIDACIÓN)
# --------------------------------------------------
class ArchivoProcessStatus(BaseModel):
    archivo_id: int
    status: str = Field(..., pattern="^(pending|processing|done|failed)$")
    progress_pct: Optional[float] = None
    message: Optional[str] = None
