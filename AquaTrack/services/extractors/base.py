# /services/extractors/base.py
from __future__ import annotations
from pydantic import BaseModel, field_validator, model_validator
from typing import List, Optional, Protocol
from datetime import date

class CanonicalLine(BaseModel):
    semana_idx: Optional[int] = None
    fecha_plan: date
    edad_dias: Optional[int] = None
    pp_g: float
    incremento_g_sem: Optional[float] = None
    sob_pct_linea: float
    retiro_org_m2: Optional[float] = None
    cosecha_flag: bool = False
    nota: Optional[str] = None

    @field_validator("pp_g")
    @classmethod
    def _pp_nonneg(cls, v: float) -> float:
        if v < 0:
            raise ValueError("pp_g must be >= 0")
        return v

    @field_validator("sob_pct_linea")
    @classmethod
    def _sob_range(cls, v: float) -> float:
        # Permitimos valores fuera de rango para luego clamp en el validador del modelo
        return v

    @field_validator("retiro_org_m2")
    @classmethod
    def _retiro_nonneg(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("retiro_org_m2 must be >= 0")
        return v

class CanonicalProjection(BaseModel):
    siembra_ventana_inicio: Optional[date] = None
    siembra_ventana_fin: Optional[date] = None
    densidad_org_m2: Optional[float] = None
    talla_inicial_g: Optional[float] = None
    sob_final_objetivo_pct: Optional[float] = None
    lineas: List[CanonicalLine]

    @model_validator(mode="after")
    def _derive_and_normalize(self):
        if not self.lineas or len(self.lineas) == 0:
            raise ValueError("empty_series")

        # Ordena por fecha
        self.lineas.sort(key=lambda x: x.fecha_plan)

        # Deriva semana_idx / edad_dias / incremento y hace clamp de SOB de línea
        base_date = self.lineas[0].fecha_plan
        for idx, ln in enumerate(self.lineas):
            if ln.semana_idx is None:
                ln.semana_idx = idx
            if ln.edad_dias is None:
                ln.edad_dias = (ln.fecha_plan - base_date).days
            # clamp SOB línea a [0,100]
            if ln.sob_pct_linea < 0:
                ln.sob_pct_linea = 0.0
            if ln.sob_pct_linea > 100:
                ln.sob_pct_linea = 100.0
            if ln.incremento_g_sem is None:
                ln.incremento_g_sem = ln.pp_g if idx == 0 else (ln.pp_g - self.lineas[idx - 1].pp_g)

        # Deriva ventanas si faltan
        if self.siembra_ventana_fin is None:
            self.siembra_ventana_fin = self.lineas[0].fecha_plan

        # Deriva sob_final_objetivo_pct si falta → última sob de las líneas
        if self.sob_final_objetivo_pct is None:
            for ln in reversed(self.lineas):
                if ln.sob_pct_linea is not None:
                    self.sob_final_objetivo_pct = ln.sob_pct_linea
                    break

        # Clamp también para sob_final_objetivo_pct
        if self.sob_final_objetivo_pct is not None:
            if self.sob_final_objetivo_pct < 0:
                self.sob_final_objetivo_pct = 0.0
            if self.sob_final_objetivo_pct > 100:
                self.sob_final_objetivo_pct = 100.0

        return self

class ExtractError(Exception):
    def __init__(self, code: str, details: str | None = None, missing: list[str] | None = None):
        super().__init__(code)
        self.code = code
        self.details = details
        self.missing = missing or []

class ProjectionExtractor(Protocol):
    def extract(self, *, file_path: str, file_name: str, file_mime: str, ciclo_id: int, granja_id: int) -> CanonicalProjection: ...
