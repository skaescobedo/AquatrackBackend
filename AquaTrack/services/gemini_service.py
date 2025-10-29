# services/gemini_service.py
"""
Servicio de integración con Google Gemini API (v1) para extraer proyecciones.
FIXED: Prompt explícito sobre incluir semana 0 con edad 0 días
"""

import json
import re
import time
from pathlib import Path

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
- densidad_org_m2 ← [densidad, density, org_m2, densidad_siembra]
- talla_inicial_g ← [talla_inicial, talla, pl_weight, peso_pl]
- sob_final_objetivo_pct ← [sob_final, survival_final, supervivencia_final, target_survival]

REGLAS CRÍTICAS PARA DETECCIÓN DE COSECHAS (cosecha_flag):

1. **Columnas a considerar:**
   - SOLO columnas con nombres: [precosecha, cosecha, harvest, retiro] (sin "acum", "total", "tot", "sum")
   - Busca celdas individuales con: "Sí", "Yes", "X", "true", o valores numéricos > 0

2. **Columnas a IGNORAR (son informativas, NO cosechas reales):**
   - Cualquier columna con: "acum", "acumulad", "total", "tot", "sum", "ingreso", "kg totales"
   - Ejemplo: "PREC. ACUM ORG/M TOT", "KG TOTALES", "INGRESO" → IGNORAR

3. **Detección de cosechas:**
   - Si hay múltiples columnas "PRECOSECHA" o "COSECHA" separadas → cada una es una cosecha_flag diferente
   - Solo marca cosecha_flag=true en filas donde retiro_org_m2 > 0
   - La ÚLTIMA cosecha del archivo debe llevar nota="cosecha_final"

4. **Validación:**
   - Si una fila tiene cosecha_flag=true PERO retiro_org_m2 es null o 0 → cambiar cosecha_flag a false
   - Asegúrate de que al menos UNA cosecha tenga retiro_org_m2 > 0

Reglas de normalización:
1. Si SOB viene como decimal (0..1), MULTIPLÍCALO por 100 para convertirlo a porcentaje
2. Ordena las líneas por fecha_plan ascendente
3. Genera semana_idx = 0, 1, 2, ... en orden INCLUYENDO LA SEMANA 0
4. Calcula edad_dias = semana_idx × 7 (la primera línea DEBE tener edad_dias = 0)
5. Calcula incremento_g_sem:
   - Para semana 0 (edad_dias = 0): incremento_g_sem = pp_g
   - Para semanas siguientes: incremento_g_sem = pp_g[actual] - pp_g[anterior]
6. Si siembra_ventana_inicio no está en el archivo → null
7. Si siembra_ventana_fin no está en el archivo → usa la primera fecha_plan de las líneas (la línea con semana_idx = 0)
8. Si sob_final_objetivo_pct no está en el archivo → usa el último sob_pct_linea de las líneas
9. Si retiro_org_m2 no está en cosechas → null (no inventar)

CRÍTICO: La primera línea del array "lineas" SIEMPRE debe tener:
- semana_idx: 0
- edad_dias: 0
- incremento_g_sem: igual a pp_g de esa primera línea

NO omitas ni elimines la línea de semana 0. Es obligatoria e importante para el sistema.

Catálogo de errores (devolver en lugar del esquema canónico si aplica):
{{
  "error": {{
    "code": "missing_required_columns",
    "details": "No se encontraron columnas esenciales (fecha, pp, sob)",
    "missing": ["fecha_plan", "pp_g", "sob_pct_linea"]
  }}
}}

Códigos de error válidos:
- "missing_required_columns": Faltan fecha, pp o sob
- "invalid_date_format": Fechas no parseables
- "no_rows_found": Archivo vacío o sin datos
- "parse_error": Estructura del archivo no reconocible
"""


# ===================================
# HELPERS
# ===================================

def _is_excel_file(mime: str, path: str) -> bool:
    """Detecta si es Excel (.xlsx o .xls)"""
    return (
            mime in ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     "application/vnd.ms-excel")
            or path.lower().endswith((".xlsx", ".xls"))
    )


def _excel_to_csv_text(file_path: str) -> str:
    """Convierte Excel a CSV en memoria"""
    import pandas as pd
    import io

    try:
        df = pd.read_excel(file_path, engine="openpyxl" if file_path.lower().endswith(".xlsx") else "xlrd")
    except Exception as e:
        raise ExtractError("excel_read_error", details=str(e))

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()


def _upload_file(client: genai.Client, *, file_path: str, file_mime: str):
    """Sube archivo a Files API de Gemini"""
    try:
        uploaded = client.files.upload(path=file_path, config=types.UploadFileConfig(mime_type=file_mime))
    except Exception as e:
        raise ExtractError("upload_failed", details=str(e))

    # Esperar a que esté listo
    max_wait = 30
    for _ in range(max_wait):
        file_info = client.files.get(name=uploaded.name)
        if file_info.state == "ACTIVE":
            return uploaded
        time.sleep(1)

    raise ExtractError("upload_timeout", details=f"File {uploaded.name} no estuvo listo en {max_wait}s")


def _part_from_uri(uploaded, file_mime: str):
    """Crea Part desde URI de archivo subido"""
    return types.Part(
        file_data=types.FileData(mime_type=file_mime, file_uri=uploaded.uri)
    )


def _extract_first_json_blob(text: str) -> str:
    """Extrae primer JSON válido del texto"""
    if not text:
        raise ValueError("Respuesta vacía del modelo.")

    # Buscar bloques markdown ```json ... ```
    fence = re.search(r"```(?:json)?\s*(\{.+?\})\s*```", text, re.DOTALL | re.IGNORECASE)
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
    """Extrae texto de la respuesta de Gemini"""
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
                detail=f"Tipo de archivo no soportado. "
                       f"Extensiones válidas: {', '.join(GeminiService.ACCEPTED_EXTENSIONS)}"
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
                        text="Devuelve EXCLUSIVAMENTE el JSON canónico descrito, o uno de los objetos de error del catálogo. RECUERDA: La primera línea del array 'lineas' DEBE tener semana_idx=0 y edad_dias=0."),
                ],
            )

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

        # --- PDF o Imagen → Files API ---
        elif mime in ("application/pdf", "image/png", "image/jpeg", "image/jpg"):
            uploaded = _upload_file(self.client, file_path=file_path, file_mime=mime)
            file_part = _part_from_uri(uploaded, mime)

            user = types.Content(
                role="user",
                parts=[
                    types.Part(text=SYSTEM_PROMPT),
                    types.Part(text=DEV_RULES),
                    types.Part(
                        text=f"Contexto: ciclo #{ciclo_id}, granja #{granja_id}. Archivo: {file_name} (mime: {file_mime})."),
                    file_part,
                    types.Part(
                        text="Devuelve EXCLUSIVAMENTE el JSON canónico descrito, o uno de los objetos de error del catálogo. RECUERDA: La primera línea del array 'lineas' DEBE tener semana_idx=0 y edad_dias=0."),
                ],
            )

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
        else:
            raise ExtractError("unsupported_mime", f"Tipo MIME no soportado: {mime}")

        # Extraer texto de respuesta
        raw_text = _coalesce_text_from_response(resp)
        if not raw_text:
            raise ExtractError("empty_response", "Gemini devolvió respuesta vacía")

        # Extraer JSON
        json_str = _extract_first_json_blob(raw_text)

        # Parsear JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ExtractError("json_parse_error", details=str(e))

        # Verificar si es error
        if "error" in data:
            err = data["error"]
            raise ExtractError(
                code=err.get("code", "unknown_error"),
                details=err.get("details"),
                missing=err.get("missing", [])
            )

        # Validar con Pydantic
        try:
            canonical = CanonicalProjection(**data)
        except Exception as e:
            raise ExtractError("validation_error", details=str(e))

        # VALIDACIÓN FINAL: Asegurar que la primera línea tenga semana_idx=0 y edad_dias=0
        if canonical.lineas:
            first_line = canonical.lineas[0]
            if first_line.semana_idx != 0:
                raise ExtractError(
                    "validation_error",
                    details=f"La primera línea debe tener semana_idx=0, pero tiene semana_idx={first_line.semana_idx}"
                )
            if first_line.edad_dias != 0:
                raise ExtractError(
                    "validation_error",
                    details=f"La primera línea debe tener edad_dias=0, pero tiene edad_dias={first_line.edad_dias}"
                )

        return canonical