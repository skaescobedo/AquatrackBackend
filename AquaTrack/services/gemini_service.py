# services/gemini_service.py
"""
Servicio de integración con Google Gemini API (v1) para extraer proyecciones.
Adaptado del código anterior exitoso.
"""

import json
import re
import time
from pathlib import Path
from typing import Iterable, Optional

from google import genai
from google.genai import types
from fastapi import HTTPException, UploadFile

from config.settings import settings
from schemas.projection import CanonicalProjection


# ===================================
# EXCEPCIONES
# ===================================

class ExtractError(Exception):
    """Error durante la extracción de datos"""

    def __init__(self, code: str, details: str | None = None, missing: list[str] | None = None):
        self.code = code
        self.details = details
        self.missing = missing or []
        super().__init__(f"{code}: {details or ''}")


# ===================================
# PROMPTS PARA GEMINI
# ===================================

SYSTEM_PROMPT = (
    "Eres un asistente de extracción de datos para acuacultura. "
    "Tu tarea es leer tablas de proyección (CSV, Excel, PDF o imagen), "
    "mapear encabezados heterogéneos a un esquema canónico y emitir EXCLUSIVAMENTE un JSON válido. "
    "No incluyas texto adicional, ni explicaciones, ni bloques markdown, ni ```json. "
    "Si faltan columnas mínimas, responde con un objeto de error estandarizado."
)

DEV_RULES = f"""
IMPORTANTE: Debes retornar EXACTAMENTE este esquema JSON, sin agregar ni cambiar nombres de campos.

Esquema canónico (copiar exactamente):
{{
  "siembra_ventana_inicio": "YYYY-MM-DD o null",
  "siembra_ventana_fin": "YYYY-MM-DD o null",
  "densidad_org_m2": número >= 0 o null,
  "talla_inicial_g": número >= 0 o null,
  "sob_final_objetivo_pct": número 0-100 o null,
  "lineas": [
    {{
      "semana_idx": número entero >= 0,
      "fecha_plan": "YYYY-MM-DD",
      "edad_dias": número entero >= 0 (múltiplo de 7),
      "pp_g": número >= 0,
      "incremento_g_sem": número >= 0,
      "sob_pct_linea": número 0-100,
      "cosecha_flag": true o false,
      "retiro_org_m2": número >= 0 o null,
      "nota": "texto" o null
    }}
  ]
}}

Reglas de mapeo de columnas del archivo:
- fecha_plan ← [fecha, fecha_semana, week_date, date, dia]
- pp_g ← [pp, peso_promedio_g, peso_promedio, avg_weight_g, peso, weight]
- sob_pct_linea ← [sob, survival, supervivencia, supervivencia_%, sob_%, survival_%]
- retiro_org_m2 ← [retiro, removal_org_m2, harvest_density, densidad_retiro]
- cosecha_flag ← [cosecha, harvest, is_harvest, es_cosecha] (detecta "Sí", "Yes", "X", true)
- densidad_org_m2 ← [densidad, density, org_m2, densidad_siembra]
- talla_inicial_g ← [talla_inicial, talla, pl_weight, peso_pl]
- sob_final_objetivo_pct ← [sob_final, survival_final, supervivencia_final, target_survival]

Reglas de normalización:
1. Si SOB viene como decimal (0..1), MULTIPLÍCALO por 100 para convertirlo a porcentaje
2. Ordena las líneas por fecha_plan ascendente
3. Genera semana_idx = 0, 1, 2, ... en orden
4. Calcula edad_dias = semana_idx × 7
5. Calcula incremento_g_sem:
   - Para semana 0: incremento_g_sem = pp_g
   - Para semanas siguientes: incremento_g_sem = pp_g[actual] - pp_g[anterior]
6. Si siembra_ventana_inicio no está en el archivo → null
7. Si siembra_ventana_fin no está en el archivo → usa la primera fecha_plan de las líneas
8. Si sob_final_objetivo_pct no está en el archivo → usa el último sob_pct_linea de las líneas
9. Máximo {settings.MAX_PROJECTION_ROWS} líneas

Validaciones:
- pp_g >= 0
- retiro_org_m2 >= 0 (si existe)
- sob_pct_linea entre 0 y 100 (si está fuera de rango, ajústalo)
- Fechas válidas en formato YYYY-MM-DD

Si hay error, responde SOLO con:
{{"error":"missing_required_columns","missing":["fecha_plan","pp_g","sob_pct_linea"]}}
{{"error":"type_error","details":"campo X no numérico"}}
{{"error":"date_parse_error","details":"fecha_plan inválida"}}
{{"error":"empty_series"}}
{{"error":"limits_exceeded","details":">{settings.MAX_PROJECTION_ROWS} filas"}}

NO agregues texto adicional, NO uses bloques markdown, retorna SOLO el JSON.
"""

# ===================================
# HELPERS PARA TIPOS DE ARCHIVO
# ===================================

_EXCEL_MIMES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",  # .xls
}


def _is_excel_file(file_mime: str, file_path: str) -> bool:
    """Detecta si es un archivo Excel por MIME o extensión"""
    mime = (file_mime or "").lower()
    if mime in _EXCEL_MIMES:
        return True
    ext = Path(file_path).suffix.lower()
    return ext in (".xlsx", ".xls")


def _excel_to_csv_text(file_path: str) -> str:
    """
    Convierte Excel a CSV en memoria (texto UTF-8).
    Toma el sheet con mayor número de filas.
    """
    try:
        import pandas as pd
    except ImportError:
        raise ExtractError(
            "excel_convert_error",
            "Falta dependencia: instala con `pip install pandas openpyxl xlrd`"
        )

    try:
        # Leer todos los sheets
        all_sheets = pd.read_excel(file_path, sheet_name=None)
        if isinstance(all_sheets, dict) and all_sheets:
            # Elegir el sheet con más filas
            def _rows(df):
                try:
                    return len(df.dropna(how="all"))
                except Exception:
                    return len(df)

            best_df = max(all_sheets.values(), key=_rows)
        else:
            best_df = pd.read_excel(file_path)

        # Normalizar columnas a string
        best_df.columns = [str(c) for c in best_df.columns]
        csv_text = best_df.to_csv(index=False)

        if not csv_text.strip():
            raise ExtractError("excel_convert_error", "Excel vacío tras conversión")

        return csv_text
    except ExtractError:
        raise
    except Exception as e:
        raise ExtractError("excel_convert_error", f"Error leyendo Excel: {e}")


# ===================================
# HELPERS PARA GEMINI FILES API
# ===================================

def _upload_file(client: genai.Client, *, file_path: str, file_mime: Optional[str]):
    """Sube archivo a Gemini Files API y espera activación"""
    clean_path = Path(file_path).resolve().as_posix()

    try:
        f = client.files.upload(file=clean_path, mime_type=file_mime) if file_mime \
            else client.files.upload(file=clean_path)
    except TypeError:
        f = client.files.upload(file=clean_path)

    # Esperar activación (con timeout)
    timeout_seconds = getattr(settings, "GEMINI_TIMEOUT_MS", 120000) / 1000.0
    deadline = time.time() + timeout_seconds
    name = getattr(f, "name", None)
    state = getattr(f, "state", None) or getattr(f, "status", None)

    while state and state not in ("ACTIVE", "READY", "SUCCEEDED", "PROCESSING_COMPLETE"):
        if time.time() > deadline:
            raise ExtractError("upload_timeout", f"Archivo no activado (state={state})")
        time.sleep(0.6)
        try:
            if name:
                f = client.files.get(name=name)
        except Exception:
            break
        state = getattr(f, "state", None) or getattr(f, "status", None)

    return f


def _part_from_uri(uploaded, fallback_mime: str | None):
    """Crea un Part de Gemini desde un archivo subido"""
    uri = getattr(uploaded, "name", None) or getattr(uploaded, "uri", None)
    if not uri:
        raise ExtractError("upload_no_name", "Archivo subido sin 'name/uri'")

    mime = getattr(uploaded, "mime_type", None) or (fallback_mime or "application/octet-stream")

    try:
        return types.Part.from_uri(file_uri=uri, mime_type=mime)
    except TypeError:
        return types.Part.from_uri(file_uri=uri)


# ===================================
# HELPERS PARA PARSEO DE RESPUESTA
# ===================================

def _extract_first_json_blob(text: str) -> str:
    """Extrae el primer JSON válido de la respuesta de Gemini"""
    if not text:
        raise ExtractError("empty_response", "Modelo sin contenido")

    # Intentar extraer de markdown fence
    fence = re.search(r"```(?:json)?\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass

    # Buscar primer objeto JSON válido
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
    """Extrae texto de la respuesta de Gemini (compatibilidad con diferentes formatos)"""
    text = getattr(resp, "text", None)
    if text:
        return text

    candidates = getattr(resp, "candidates", None)
    if candidates:
        cand0 = candidates[0]
        content = getattr(cand0, "content", None)
        if content and getattr(content, "parts", None):
            pieces: list[str] = []
            for p in content.parts:
                t = getattr(p, "text", None)
                if t:
                    pieces.append(t)
            joined = "".join(pieces)
            if joined:
                return joined

    return ""


# ===================================
# SERVICIO PRINCIPAL
# ===================================

class GeminiService:
    """Servicio para extraer proyecciones con Google Gemini"""

    # Tipos MIME aceptados
    ACCEPTED_MIMETYPES = {
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'text/csv',
        'application/pdf',
        'image/png',
        'image/jpeg',
        'image/jpg',
    }

    ACCEPTED_EXTENSIONS = {'.xlsx', '.xls', '.csv', '.pdf', '.png', '.jpg', '.jpeg'}

    def __init__(self):
        """Inicializa el cliente de Gemini"""
        if not settings.GEMINI_API_KEY:
            raise ExtractError("missing_api_key", "GEMINI_API_KEY no configurada en .env")

        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(api_version="v1"),
        )

    @staticmethod
    def validate_file(file: UploadFile) -> None:
        """Valida que el archivo sea de un tipo soportado"""
        # Validar extensión
        extension = Path(file.filename).suffix.lower()
        if extension not in GeminiService.ACCEPTED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"Tipo de archivo no soportado. Extensiones válidas: {', '.join(GeminiService.ACCEPTED_EXTENSIONS)}"
            )

        # Validar MIME type si está disponible
        if file.content_type and file.content_type not in GeminiService.ACCEPTED_MIMETYPES:
            import mimetypes
            guessed_type = mimetypes.guess_type(file.filename)[0]
            if guessed_type not in GeminiService.ACCEPTED_MIMETYPES:
                raise HTTPException(
                    status_code=415,
                    detail=f"Tipo MIME no soportado: {file.content_type}"
                )

    async def extract_from_file(
            self,
            *,
            file_path: str,
            file_name: str,
            file_mime: str,
            ciclo_id: int,
            granja_id: int,
    ) -> CanonicalProjection:
        """
        Extrae proyección desde un archivo usando Gemini.

        Soporta:
        - CSV: se envía como texto
        - Excel: se convierte a CSV y se envía como texto
        - PDF/Imagen: se sube a Files API

        Returns:
            CanonicalProjection validada
        """
        mime = (file_mime or "").lower()

        # --- CSV directo o Excel → CSV (texto) ---
        if mime == "text/csv" or _is_excel_file(file_mime, file_path):
            if _is_excel_file(file_mime, file_path):
                csv_text = _excel_to_csv_text(file_path)
                display_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
                    if file_path.lower().endswith(".xlsx") else "application/vnd.ms-excel"
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
                    types.Part(
                        text=f"Contexto: ciclo #{ciclo_id}, granja #{granja_id}. Archivo: {file_name} (mime: {display_mime})."),
                    types.Part(text="Contenido CSV (texto plano) a continuación:"),
                    types.Part(text=csv_text),
                    types.Part(
                        text="Devuelve EXCLUSIVAMENTE el JSON canónico descrito, o uno de los objetos de error del catálogo."),
                ],
            )

            # Llamada con temperature=0 (determinista)
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
                    types.Part(
                        text=f"Contexto: ciclo #{ciclo_id}, granja #{granja_id}. Archivo: {file_name} (mime: {file_mime})."),
                    types.Part(
                        text="Devuelve EXCLUSIVAMENTE el JSON canónico descrito, o uno de los objetos de error del catálogo."),
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
            raise ExtractError("unsupported_mime", details=f"No soportado: {file_mime}")

        # ---------- Parseo de respuesta ----------
        text = _coalesce_text_from_response(resp)
        json_str = _extract_first_json_blob(text)

        try:
            data = json.loads(json_str)
        except Exception as e:
            raise ExtractError("invalid_json", f"No se pudo parsear JSON: {e}")

        # Verificar si es un error
        if isinstance(data, dict) and "error" in data:
            raise ExtractError(
                str(data.get("error")),
                details=data.get("details"),
                missing=data.get("missing") or []
            )

        # Validar con Pydantic
        try:
            canonical = CanonicalProjection.model_validate(data)
        except Exception as e:
            raise ExtractError("schema_validation_error", details=str(e))

        # Validar límite de filas
        if len(canonical.lineas) > settings.MAX_PROJECTION_ROWS:
            raise ExtractError("limits_exceeded", details=f">{settings.MAX_PROJECTION_ROWS} filas")

        return canonical