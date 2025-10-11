# /services/extractors/gemini_extractor.py
from __future__ import annotations

"""
Extractor para archivos de proyección usando el SDK nuevo google-genai (API v1).
- Usa `from google import genai` y `from google.genai import types`.
- CSV: se envía como texto plano dentro de parts (no como archivo subido).
- Excel (.xlsx/.xls): se convierte localmente a CSV (texto) y se envía como CSV.
- PDF/imagen: se suben con `client.files.upload(...)` y se referencian con `types.Part.from_uri(...)`.
- Evitamos response_mime_type por incompatibilidades; usamos temperature=0 cuando el SDK lo soporta.
- Extrae el primer bloque JSON válido y valida contra el esquema canónico.
"""

import json
import re
import time
from pathlib import Path
from typing import Iterable, Optional

from google import genai
from google.genai import types

from services.extractors.base import CanonicalProjection, ExtractError, ProjectionExtractor
from config.settings import settings


# ------------------------------ Prompts ------------------------------ #
# ------------------------------ Prompts ------------------------------ #
SYSTEM_PROMPT = (
    "Eres un asistente de extracción de datos para acuacultura. "
    "Tu tarea es leer tablas de proyección (CSV, Excel, PDF o imagen), "
    "mapear encabezados heterogéneos a un esquema canónico y emitir EXCLUSIVAMENTE un JSON válido. "
    "No incluyas texto adicional, ni explicaciones, ni bloques markdown, ni ```json. "
    "Si faltan columnas mínimas, responde con un objeto de error estandarizado."
)

DEV_RULES = f"""
Esquema canónico (JSON que debes devolver):
- Campos top-level (opcionales): 
  - siembra_ventana_inicio (YYYY-MM-DD)
  - siembra_ventana_fin (YYYY-MM-DD)
  - densidad_org_m2 (>0)
  - talla_inicial_g (>=0)
  - sob_final_objetivo_pct (0..100)
- lineas: array de objetos con campos:
  - semana_idx (int >=0, derivable)
  - fecha_plan (YYYY-MM-DD)
  - edad_dias (int >=0, derivable)
  - pp_g (number >=0)
  - incremento_g_sem (number >=0, derivable)
  - sob_pct_linea (0..100, si viene 0..1 MULTIPLICA por 100)
  - retiro_org_m2 (number >=0, opcional)
  - cosecha_flag (boolean)
  - nota (string opcional)

Reglas de normalización y derivación:
- Acepta encabezados sinónimos:
  - fecha_plan ≈ [fecha, fecha_semana, week_date]
  - pp_g ≈ [pp, peso_promedio_g, avg_weight_g]
  - sob_pct_linea ≈ [sob, survival, supervivencia_%, survival_%]
  - retiro_org_m2 ≈ [retiro, removal_org_m2, harvest_density]
  - cosecha_flag ≈ [cosecha, harvest, is_harvest]
  - siembra_ventana_inicio ≈ [siembra_inicio, ventana_inicio, start_window, ventana_siembra_inicio]
  - siembra_ventana_fin ≈ [siembra_fin, ventana_fin, end_window, ventana_siembra_fin]
  - sob_final_objetivo_pct ≈ [sob_final, survival_final, supervivencia_final_%]
- Normaliza fechas a YYYY-MM-DD y ordena las lineas por fecha ascendente.
- Si sob viene 0..1, MULTIPLICA por 100 (aplica a sob_pct_linea y sob_final_objetivo_pct si aparece en 0..1).
- Deriva semana_idx (0..N) y edad_dias (0,7,14,...) si faltan.
- Deriva incremento_g_sem si falta: incremento_g_sem[n] = pp_g[n] - pp_g[n-1]; para n=0, incremento_g_sem = pp_g[0].
- Si NO viene siembra_ventana_inicio, déjala null (NO la derives).
- Si NO viene siembra_ventana_fin, usa la PRIMERA fecha_plan de lineas.
- Si NO viene sob_final_objetivo_pct, usa la ÚLTIMA sob_pct_linea NO nula (después de normalizada a 0..100). Si no hubiera sob en lineas, deja null.
- No inventes filas; máximo {settings.MAX_PROJECTION_ROWS} filas.

Validaciones y clamping:
- pp_g >= 0, retiro_org_m2 >= 0, SOB en 0..100. Si alguna SOB queda fuera, haz clamp a [0,100].
- Las fechas de lineas deben ser semanales (saltos de 7 días) en lo posible; si hay pequeñas inconsistencias, ordénalas y conserva las filas válidas.

Errores (responder SOLO con uno de estos JSONs si aplica):
- {{"error":"missing_required_columns","missing":["fecha_plan","pp_g","sob_pct_linea"]}}
- {{"error":"type_error","details":"pp_g no numérico en filas 3,4"}}
- {{"error":"date_parse_error","details":"fecha_plan '13-32-2025' inválida"}}
- {{"error":"empty_series"}}
- {{"error":"limits_exceeded","details":">{settings.MAX_PROJECTION_ROWS} filas"}}
"""



# ------------------------------ Helpers MIME/EXT ------------------------------ #
_EXCEL_MIMES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",                                           # .xls
}

def _is_excel_file(file_mime: str, file_path: str) -> bool:
    mime = (file_mime or "").lower()
    if mime in _EXCEL_MIMES:
        return True
    ext = Path(file_path).suffix.lower()
    return ext in (".xlsx", ".xls")


def _excel_to_csv_text(file_path: str) -> str:
    """
    Convierte Excel (xlsx/xls) a CSV en memoria (texto, UTF-8, sin índice).
    - Toma el sheet con mayor número de filas no vacías (o el primero disponible).
    - Requiere: pandas + openpyxl (xlsx) / xlrd (xls).
    """
    try:
        import pandas as pd  # type: ignore
    except Exception:
        raise ExtractError(
            "excel_convert_error",
            "Falta dependencia: instala con `pip install pandas openpyxl xlrd`"
        )

    try:
        # Lee todos los sheets para elegir el mejor candidato
        all_sheets = pd.read_excel(file_path, sheet_name=None)
        if isinstance(all_sheets, dict) and all_sheets:
            # prioriza el sheet con más filas (no nulas)
            def _rows(df):
                try:
                    return len(df.dropna(how="all"))
                except Exception:
                    return len(df)
            best_df = max(all_sheets.values(), key=_rows)
        else:
            # fallback: intenta lectura simple
            best_df = pd.read_excel(file_path)

        # Normaliza columnas a str (evitar mix types raros)
        best_df.columns = [str(c) for c in best_df.columns]
        csv_text = best_df.to_csv(index=False)
        if not csv_text.strip():
            raise ExtractError("excel_convert_error", "Excel vacío tras la conversión")
        return csv_text
    except ExtractError:
        raise
    except Exception as e:
        raise ExtractError("excel_convert_error", f"Error leyendo Excel: {e}")


# ------------------------------ Files API helpers ------------------------------ #
def _upload_file(client: genai.Client, *, file_path: str, file_mime: Optional[str]):
    clean_path = Path(file_path).resolve().as_posix()

    try:
        f = client.files.upload(file=clean_path, mime_type=file_mime) if file_mime \
            else client.files.upload(file=clean_path)
    except TypeError:
        f = client.files.upload(file=clean_path)

    deadline = time.time() + (settings.GEMINI_TIMEOUT_MS / 1000.0 if getattr(settings, "GEMINI_TIMEOUT_MS", None) else 120.0)
    name = getattr(f, "name", None)
    state = getattr(f, "state", None) or getattr(f, "status", None)
    while state and state not in ("ACTIVE", "READY", "SUCCEEDED", "PROCESSING_COMPLETE"):
        if time.time() > deadline:
            raise ExtractError("upload_timeout", f"El archivo no se activó a tiempo (state={state}).")
        time.sleep(0.6)
        try:
            if name:
                f = client.files.get(name=name)
        except Exception:
            break
        state = getattr(f, "state", None) or getattr(f, "status", None)
    return f


def _part_from_uri(uploaded, fallback_mime: str | None):
    uri = getattr(uploaded, "name", None) or getattr(uploaded, "uri", None)
    if not uri:
        raise ExtractError("upload_no_name", "El archivo subido no expuso 'name/uri'")
    mime = getattr(uploaded, "mime_type", None) or (fallback_mime or "application/octet-stream")
    try:
        return types.Part.from_uri(file_uri=uri, mime_type=mime)
    except TypeError:
        return types.Part.from_uri(file_uri=uri)


def _extract_first_json_blob(text: str) -> str:
    if not text:
        raise ExtractError("empty_response", "Modelo sin contenido")

    fence = re.search(r"```(?:json)?\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass

    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start: i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except Exception:
                        break

    return text


def _coalesce_text_from_response(resp) -> str:
    text = getattr(resp, "text", None)
    if text:
        return text
    candidates = getattr(resp, "candidates", None)
    if candidates:
        cand0 = candidates[0]
        content = getattr(cand0, "content", None)
        if content and getattr(content, "parts", None):
            pieces: Iterable[str] = []
            for p in content.parts:  # type: ignore[attr-defined]
                t = getattr(p, "text", None)
                if t:
                    pieces = [*pieces, t]
            joined = "".join(pieces)
            if joined:
                return joined
    return ""


# ------------------------------ Extractor ------------------------------ #
class GeminiExtractor(ProjectionExtractor):
    """Extractor de proyecciones con google-genai (API v1)."""

    def __init__(self):
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise ExtractError("missing_api_key", "GEMINI_API_KEY no configurada")

        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version="v1"),
        )

    def extract(
        self,
        *,
        file_path: str,
        file_name: str,
        file_mime: str,
        ciclo_id: int,
        granja_id: int,
    ) -> CanonicalProjection:
        """Ejecuta el flujo de extracción y devuelve un CanonicalProjection validado."""

        mime = (file_mime or "").lower()

        # --- CSV directo o Excel -> CSV (texto) ---
        if mime == "text/csv" or _is_excel_file(file_mime, file_path):
            if _is_excel_file(file_mime, file_path):
                csv_text = _excel_to_csv_text(file_path)
                display_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_path.lower().endswith(".xlsx") else "application/vnd.ms-excel"
            else:
                try:
                    csv_text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    raise ExtractError("file_read_error", details=str(e))
                display_mime = "text/csv"

            user = types.Content(
                role="user",
                parts=[
                    types.Part(text=SYSTEM_PROMPT),
                    types.Part(text=DEV_RULES),
                    types.Part(text=f"Contexto: ciclo #{ciclo_id}, granja #{granja_id}. Archivo: {file_name} (mime: {display_mime})."),
                    types.Part(text="Contenido CSV (texto plano) a continuación:"),
                    types.Part(text=csv_text),
                    types.Part(text="Devuelve EXCLUSIVAMENTE el JSON canónico descrito, o uno de los objetos de error del catálogo."),
                ],
            )

            # Llamada robusta (sin response_mime_type). Forzamos temperature=0 si la firma lo permite.
            try:
                resp = self.client.models.generate_content(
                    model=settings.GEMINI_MODEL_ID,
                    contents=[user],
                    generation_config=types.GenerationConfig(temperature=0),
                )
            except TypeError:
                try:
                    resp = self.client.models.generate_content(
                        model=settings.GEMINI_MODEL_ID,
                        contents=[user],
                        generation_config={"temperature": 0},
                    )
                except TypeError:
                    resp = self.client.models.generate_content(
                        model=settings.GEMINI_MODEL_ID,
                        contents=[user],
                    )

        # --- PDF/imagen: subir + Part.from_uri ---
        elif mime.startswith("application/pdf") or mime.startswith("image/"):
            uploaded = _upload_file(self.client, file_path=file_path, file_mime=file_mime)
            file_part = _part_from_uri(uploaded, file_mime)

            user = types.Content(
                role="user",
                parts=[
                    types.Part(text=SYSTEM_PROMPT),
                    types.Part(text=DEV_RULES),
                    file_part,
                    types.Part(text=f"Contexto: ciclo #{ciclo_id}, granja #{granja_id}. Archivo: {file_name} (mime: {file_mime})."),
                    types.Part(text="Devuelve EXCLUSIVAMENTE el JSON canónico descrito, o uno de los objetos de error del catálogo."),
                ],
            )

            try:
                resp = self.client.models.generate_content(
                    model=settings.GEMINI_VISION_MODEL_ID,
                    contents=[user],
                    generation_config=types.GenerationConfig(temperature=0),
                )
            except TypeError:
                try:
                    resp = self.client.models.generate_content(
                        model=settings.GEMINI_VISION_MODEL_ID,
                        contents=[user],
                        generation_config={"temperature": 0},
                    )
                except TypeError:
                    resp = self.client.models.generate_content(
                        model=settings.GEMINI_VISION_MODEL_ID,
                        contents=[user],
                    )
        else:
            # Otros binarios (xlsx/xls quedan cubiertos por la ruta Excel->CSV)
            raise ExtractError("unsupported_mime", details=f"No soportado en v1: {file_mime}. Convierte a CSV o PDF.")

        # ---------- Parseo de respuesta ----------
        text = _coalesce_text_from_response(resp)
        json_str = _extract_first_json_blob(text)

        try:
            data = json.loads(json_str)
        except Exception as e:
            raise ExtractError("invalid_json", f"No se pudo parsear JSON: {e}")

        if isinstance(data, dict) and "error" in data:
            raise ExtractError(str(data.get("error")), details=data.get("details"), missing=data.get("missing") or [])

        try:
            canonical = CanonicalProjection.model_validate(data)
        except Exception as e:
            raise ExtractError("schema_validation_error", details=str(e))

        if len(canonical.lineas) > settings.MAX_PROJECTION_ROWS:
            raise ExtractError("limits_exceeded", details=f">{settings.MAX_PROJECTION_ROWS} filas")

        return canonical
