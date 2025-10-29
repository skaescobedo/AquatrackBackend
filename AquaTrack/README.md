# 🦐 AquaTrack Backend

Sistema de gestión y proyección inteligente para cultivo de camarón en acuacultura.

**Stack**: Python 3.11+ • FastAPI • SQLAlchemy • MySQL • Google Gemini AI

---

## 📊 Arquitectura del Sistema

### Módulos Implementados

```
AquaTrack/
├── api/                    # Endpoints REST
│   ├── auth.py            # Autenticación JWT
│   ├── farms.py           # CRUD granjas
│   ├── ponds.py           # CRUD estanques
│   ├── cycles.py          # Ciclos (CON proyección opcional)
│   ├── seeding.py         # Planes de siembra
│   ├── biometria.py       # Biometrías + SOB operativo
│   ├── harvest.py         # Olas y líneas de cosecha
│   └── projections.py     # Proyecciones con Gemini AI
│
├── services/
│   ├── gemini_service.py       # Extractor IA (Excel/CSV/PDF/imágenes)
│   ├── projection_service.py   # Lógica de proyecciones + auto-setup
│   ├── cycle_service.py
│   ├── seeding_service.py
│   ├── biometria_service.py
│   └── harvest_service.py
│
├── models/               # SQLAlchemy ORM
├── schemas/              # Pydantic DTOs
├── utils/                # Helpers (datetime, permisos, DB)
└── config/               # Settings (Pydantic)
```

---

## 🗄️ Modelo de Datos

### Jerarquía Principal

```
Usuario ↔ UsuarioGranja ↔ Granja ↔ Estanques
                          ↓
                       Ciclos ← CicloResumen (al cerrar)
                          ↓
         ┌────────────────┼────────────────┐
         ↓                ↓                ↓
    Proyeccion      SiembraPlan      CosechaOla
         ↓                ↓                ↓
  ProyeccionLinea  SiembraEstanque  CosechaEstanque
                        ↓
                   Biometria
                        ↓
                  SOBCambioLog
```

### Estados Clave

| Entidad | Campo | Valores | Descripción |
|---------|-------|---------|-------------|
| `Usuario` | `status` | `a`/`i` | Activo / Inactivo |
| `Granja` | `is_active` | `1`/`0` | Operativa / Desactivada |
| `Estanque` | `status` | `i`/`a`/`c`/`m` | Inactivo / Activo / Cosecha / Mantenimiento |
| `Estanque` | `is_vigente` | `1`/`0` | Vigente / Baja administrativa |
| `Ciclo` | `status` | `a`/`t` | Activo / Terminado |
| `SiembraPlan` | `status` | `p`/`e`/`f` | Planeado / Ejecución / Finalizado |
| `SiembraEstanque` | `status` | `p`/`f` | Pendiente / Finalizada |
| `Proyeccion` | `status` | `b`/`p`/`r`/`x` | Borrador / Publicada / Reforecast / Cancelada |
| `Proyeccion` | `source_type` | `archivo`/`planes`/`reforecast` | Origen de la proyección |
| `CosechaOla` | `tipo` | `p`/`f` | Parcial / Final |
| `CosechaOla` | `status` | `p`/`r`/`x` | Pendiente / Realizada / Cancelada |
| `CosechaEstanque` | `status` | `p`/`c`/`x` | Pendiente / Confirmada / Cancelada |

---

## 🎯 Funcionalidades Core

### 1. Gestión de Granjas y Estanques
- CRUD completo con validación de superficie total
- Estanques con estados operativos y bandera `is_vigente`
- Validación: suma de estanques vigentes ≤ superficie total de granja

### 2. Ciclos de Producción
- **Restricción crítica**: 1 solo ciclo activo por granja
- Estados: `a` (activo) → `t` (terminado)
- Resumen automático al cerrar ciclo (SOB final, toneladas, kg/ha)
- **NUEVO**: Creación con proyección opcional (archivo procesado con Gemini)

### 3. Proyecciones con IA (Gemini) 🤖

#### Ingesta desde Archivo
```
Usuario sube archivo (Excel/CSV/PDF/imagen)
  ↓
GeminiService procesa con prompt estructurado
  ↓
CanonicalProjection (JSON normalizado)
  ↓
ProjectionService crea Proyeccion + ProyeccionLinea
  ↓
Auto-setup condicional (planes + olas)
```

**Formatos soportados**:
- Excel: `.xlsx`, `.xls` (convierte a CSV → texto)
- CSV: `.csv` (directo como texto)
- PDF: `.pdf` (Files API)
- Imágenes: `.png`, `.jpg`, `.jpeg` (Vision API)

**Normalización automática**:
- Mapea encabezados heterogéneos → campos canónicos
- Deriva: `semana_idx`, `edad_dias`, `incremento_g_sem`
- Convierte SOB 0..1 → 0..100 automáticamente
- Interpola campos faltantes (`siembra_ventana_fin`, `sob_final_objetivo_pct`)

**Esquema Canónico (CanonicalProjection)**:
```python
{
  "siembra_ventana_inicio": date | None,
  "siembra_ventana_fin": date | None,
  "densidad_org_m2": float | None,
  "talla_inicial_g": float | None,
  "sob_final_objetivo_pct": float | None,
  "lineas": [
    {
      "semana_idx": int,          # 0, 1, 2, ...
      "fecha_plan": date,          # YYYY-MM-DD
      "edad_dias": int,            # 0, 7, 14, ...
      "pp_g": float,               # Peso promedio
      "incremento_g_sem": float,   # Ganancia semanal
      "sob_pct_linea": float,      # Supervivencia (0-100)
      "cosecha_flag": bool,        # Marca cosecha
      "retiro_org_m2": float | None,
      "nota": str | None
    }
  ]
}
```

#### Auto-setup Condicional

**Reglas de Siembras**:
```python
NO existe plan              → ✅ Crear plan + siembras distribuidas
Plan en estado 'p'          → ✅ Actualizar plan + recrear siembras
Plan en estado 'e' o 'f'    → ❌ NO tocar (solo crea proyección)
```

**Reglas de Cosechas**:
```python
NO existen olas             → ✅ Crear olas desde líneas con cosecha_flag
Olas en estado 'p'          → ✅ Recrear olas desde proyección
Olas en estado 'r'          → ❌ NO tocar (solo crea proyección)
```

**Distribución de fechas**:
- Siembras: uniformemente entre `ventana_inicio` y `ventana_fin`
- Cosechas: uniformemente entre ventanas de cada ola

#### Versionamiento

- **V1**: Se autopublica al crear (primera proyección del ciclo)
- **V2+**: Quedan en borrador (`status='b'`)
- **Restricciones**:
  - Solo 1 proyección publicada (`is_current=True`) por ciclo
  - Solo 1 borrador (`status='b'`) por ciclo
  - No se puede cancelar la proyección actual

**Flujos**:
```python
# Crear ciclo sin proyección
POST /cycles/farms/{granja_id}

# Subir proyección después
POST /projections/cycles/{ciclo_id}/from-file

# O crear ciclo + proyección juntos (1 paso)
POST /cycles/farms/{granja_id}
  + file (opcional)
  → Crea ciclo + proyección V1 + auto-setup
```

### 4. Siembras

#### Plan Único por Ciclo
- Estados: `p` (planeado) → `e` (ejecución) → `f` (finalizado)
- Auto-generación de siembras distribuidas uniformemente
- Overrides por estanque (densidad/talla)

#### Confirmación Automática
- Al confirmar siembra → estanque pasa a `status='a'` (activo)
- Se fija `fecha_real`, `densidad_real`, `talla_real`
- Logs de reprogramación en `siembra_fecha_log`

### 5. Biometrías

#### Fecha en Zona Horaria
- Fijada por servidor en `America/Mazatlan` (naive para MySQL)
- Cálculo automático de PP e incremento semanal

#### Sistema de SOB Operativo
```python
Al sembrar:
  SOB base = 100% automático

Primera biometría:
  Puede usar 100% inicial o actualizarlo

Biometrías posteriores:
  Solo actualiza si hay cambios reales (actualiza_sob_operativa=True)
```

- Registro en `sob_cambio_log` cuando actualiza SOB
- **Restricción**: Solo editable si NO actualizó SOB (auditoría)

### 6. Cosechas

#### Olas de Cosecha (sin plan maestro)
- Tipo: `p` (parcial) o `f` (final)
- Auto-generación de líneas para todos los estanques del ciclo
- Estados: `p` → `r` (realizada) o `x` (cancelada)

#### Confirmación Inteligente
- Obtiene PP de última biometría automáticamente
- **Flexibilidad**:
  ```python
  Si provees biomasa_kg      → deriva densidad_retirada_org_m2
  Si provees densidad_org_m2 → deriva biomasa_kg
  ```
- **Fórmulas**:
  ```python
  densidad = (biomasa_kg × 1000) / (pp_g × area_m2)
  biomasa  = (densidad × area_m2 × pp_g) / 1000
  ```
- Logs de reprogramación en `cosecha_fecha_log`
- Cancelación masiva de olas: marca ola + todas las líneas pendientes

---

## 🔌 API Endpoints

### Autenticación
```
POST   /auth/register              # Registro de usuario
POST   /auth/login                 # Login (retorna JWT)
GET    /auth/me                    # Usuario actual
```

### Granjas
```
POST   /farms                      # Crear granja
GET    /farms                      # Listar granjas del usuario
GET    /farms/{id}                 # Detalle de granja
PATCH  /farms/{id}                 # Actualizar granja
DELETE /farms/{id}                 # Desactivar granja
```

### Estanques
```
POST   /ponds/farms/{granja_id}   # Crear estanque
GET    /ponds/farms/{granja_id}   # Listar estanques
GET    /ponds/{id}                 # Detalle de estanque
PATCH  /ponds/{id}                 # Actualizar estanque
POST   /ponds/{id}/deactivate     # Dar de baja
```

### Ciclos
```
POST   /cycles/farms/{granja_id}         # Crear ciclo (+ proyección opcional)
GET    /cycles/farms/{granja_id}/active  # Ciclo activo
GET    /cycles/farms/{granja_id}         # Listar ciclos
GET    /cycles/{ciclo_id}                # Detalle de ciclo
PATCH  /cycles/{ciclo_id}                # Actualizar ciclo
POST   /cycles/{ciclo_id}/close          # Cerrar ciclo
GET    /cycles/{ciclo_id}/resumen        # Resumen (si cerrado)
```

### Proyecciones (IA)
```
POST   /projections/cycles/{ciclo_id}/from-file  # Subir archivo (Gemini)
GET    /projections/cycles/{ciclo_id}            # Listar proyecciones
GET    /projections/cycles/{ciclo_id}/current    # Proyección actual
GET    /projections/cycles/{ciclo_id}/draft      # Borrador actual
GET    /projections/{proyeccion_id}              # Detalle con líneas
PATCH  /projections/{proyeccion_id}              # Actualizar metadatos
POST   /projections/{proyeccion_id}/publish      # Publicar borrador
DELETE /projections/{proyeccion_id}              # Cancelar
```

### Siembras
```
POST   /seeding/cycles/{ciclo_id}/plan          # Crear plan + siembras
GET    /seeding/cycles/{ciclo_id}/plan          # Ver plan
GET    /seeding/plans/{plan_id}/seedings        # Listar siembras
POST   /seeding/lines/{line_id}/confirm         # Confirmar siembra
POST   /seeding/lines/{line_id}/reprogram       # Reprogramar
```

### Biometrías
```
POST   /biometria/cycles/{ciclo_id}/ponds/{estanque_id}  # Registrar
GET    /biometria/cycles/{ciclo_id}/ponds/{estanque_id}  # Listar por estanque
GET    /biometria/cycles/{ciclo_id}                      # Listar por ciclo
GET    /biometria/{biometria_id}                         # Detalle
PATCH  /biometria/{biometria_id}                         # Actualizar
DELETE /biometria/{biometria_id}                         # Eliminar
```

### Cosechas
```
POST   /harvest/cycles/{ciclo_id}/waves         # Crear ola + líneas
GET    /harvest/cycles/{ciclo_id}/waves         # Listar olas
GET    /harvest/waves/{wave_id}                 # Detalle de ola
GET    /harvest/waves/{wave_id}/lines           # Líneas de ola
POST   /harvest/waves/{wave_id}/cancel          # Cancelar ola
POST   /harvest/lines/{line_id}/reprogram       # Reprogramar línea
POST   /harvest/lines/{line_id}/confirm         # Confirmar cosecha
```

---

## 🧮 Zona Horaria

**Unificada**: `America/Mazatlan` (UTC-7)

```python
# utils/datetime_utils.py

def now_mazatlan() -> datetime:
    """Retorna datetime naive en zona Mazatlán"""
    return datetime.now(pytz.timezone('America/Mazatlan')).replace(tzinfo=None)

def today_mazatlan() -> date:
    """Retorna date en zona Mazatlán"""
    return now_mazatlan().date()
```

**Uso**:
- Todas las fechas de servidor (biometrías, logs)
- Timestamps `created_at`, `updated_at`
- MySQL almacena como DATETIME sin zona (naive)

---

## ⚙️ Variables de Entorno (.env)

```env
# Base de datos
DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/aquatrack_bd

# JWT
SECRET_KEY=tu_secret_key_seguro_64_caracteres
ACCESS_TOKEN_EXPIRE_MINUTES=720
ALGORITHM=HS256

# CORS
CORS_ALLOW_ORIGINS=["http://localhost:4200","http://localhost:3000"]

# Gemini API
GEMINI_API_KEY=tu_api_key_de_google_gemini
GEMINI_MODEL_ID=models/gemini-2.0-flash-exp
GEMINI_VISION_MODEL_ID=models/gemini-2.0-flash-exp
GEMINI_TIMEOUT_MS=120000

# Proyecciones
MAX_PROJECTION_ROWS=200
PROJECTION_EXTRACTOR=gemini
```

---

## 📐 Reglas de Negocio

### Pond-First Philosophy
- Superficie de estanques vigentes ≤ superficie total de granja
- Densidades y áreas definen límites de siembra
- Validaciones en tiempo de creación/actualización

### Estados Operativos
```python
Estanque 'i' (inactivo) → puede activarse con siembra
Estanque 'a' (activo)   → tiene ciclo en curso
Estanque 'c' (cosecha)  → en proceso de cosecha
Estanque 'm' (mant.)    → fuera de operación
```

### SOB Operativo
```python
SOB base (siembra)      = 100%
SOB después de bio      = valor medido (si actualiza_sob_operativa=True)
SOB después de cosecha  = SOB_antes × (1 - retiro/densidad_base)
```

### Logs de Auditoría
- `siembra_fecha_log`: Cambios en fechas de siembra
- `cosecha_fecha_log`: Cambios en fechas de cosecha
- `sob_cambio_log`: Cambios en SOB operativo (con fuente)

---

## 🔮 Módulos Pendientes

### 1. Reforecast Automático
Sistema que actualiza borrador de proyección cuando hay eventos operativos:

**Triggers**:
- Biometrías nuevas → ancla PP/SOB real, recalibra futuro
- Siembra confirmada → shift de timeline completa
- Cosecha confirmada → ajusta retiros y SOB futuro
- Cambios en densidad → recalcula SOB final objetivo

**Lógica**:
```python
# Agregación ponderada por población
PP_granja = Σ(PP_estanque × org_estimados) / Σ(org_estimados)
  donde org_estimados = (densidad_base - retiros) × area × (SOB/100)

# Interpolación con curvas
PP: s-curve (crecimiento sigmoidea)
SOB: linear (mortalidad gradual)

# Anclajes
Semanas con datos reales → fijas
Semanas futuras → interpoladas desde último anclaje
```

**Características del código anterior aprovechables**:
- Sistema de anclajes con notas (`obs_pp:`, `obs_sob:`)
- Agregación ponderada por población real
- Ventana de fin de semana (Sábado-Domingo)
- Interpolación con curvas suaves
- Validación de cobertura mínima (30%, mín 3 estanques)
- Modo "soft" (no sobrescribe borradores manuales)

**Estructura a implementar**:
```
services/reforecast_service.py
├── get_or_create_reforecast_draft()
├── trigger_biometria_reforecast()
├── trigger_siembra_reforecast()
├── trigger_cosecha_reforecast()
├── calc_farm_weighted_pp_sob()
├── recalibrate_future_from_anchors()
├── recalibrate_timeline_shift()
└── recalculate_sob_final_objetivo()
```

**Settings**:
```python
REFORECAST_ENABLED: bool = True
REFORECAST_MIN_COVERAGE_PCT: float = 30.0
REFORECAST_MIN_PONDS: int = 3
REFORECAST_WEEKEND_MODE: bool = True
REFORECAST_WINDOW_DAYS: int = 1
```

### 2. Cálculos Agregados
`services/calculation_service.py` para métricas y analytics:
- Biomasa total por granja/estanque
- PP ponderado real vs proyectado
- SOB agregado con densidades reales
- kg/ha real y proyectado
- Comparativos semanales

### 3. Endpoints de Analytics
`api/analytics.py` para dashboards:
- `GET /analytics/cycles/{id}/biomass`
- `GET /analytics/cycles/{id}/comparison`
- `GET /analytics/cycles/{id}/weekly-report`

### 4. Sistema de Roles Avanzado
- Permisos granulares por operación
- Roles personalizados por granja

---

## 📊 Métricas del Proyecto

```
📦 Módulos implementados:     8/12 (67%)
📋 Líneas de código:          ~5,500
🗄️ Tablas BD:                 20
🔌 Endpoints:                 50+
🤖 Integración IA:            Google Gemini API v1
```

---

## 🎯 Estado Actual

**✅ Completado**:
- Autenticación JWT
- CRUD Granjas + Estanques
- Gestión de Ciclos
- Sistema de Siembras
- Biometrías con SOB operativo
- Cosechas (olas + líneas)
- **Proyecciones con Gemini AI**
- **Auto-setup condicional**
- **Versionamiento inteligente**
- Logs de auditoría
- Validaciones pond-first
- Zona horaria unificada

**🚧 En Desarrollo**:
- Reforecast automático (siguiente prioridad)
- Cálculos agregados
- Analytics endpoints

---

## 🔧 Stack Técnico

**Backend**:
- Python 3.11+
- FastAPI 0.115.0
- SQLAlchemy 2.0.35
- Pydantic 2.9.2
- PyMySQL 1.1.1

**IA**:
- Google Gemini API (SDK v1: `google-genai==1.0.0`)
- Modelos: `gemini-2.0-flash-exp` (texto), `gemini-2.0-flash-exp` (vision)

**Procesamiento de Archivos**:
- pandas 2.2.3
- openpyxl 3.1.5 (Excel)
- xlrd 2.0.1 (Excel legacy)

**Seguridad**:
- python-jose 3.3.0 (JWT)
- passlib 1.7.4 + bcrypt 4.2.0

**Base de Datos**:
- MySQL 8.0+
- Charset: utf8mb4
- Collation: utf8mb4_unicode_ci

---

## 📁 Estructura de Archivos Clave

```
AquaTrack/
├── models/
│   ├── projection.py           # Proyeccion + ProyeccionLinea + SourceType
│   └── ...
│
├── schemas/
│   ├── projection.py           # CanonicalProjection + DTOs
│   └── ...
│
├── services/
│   ├── gemini_service.py       # Extractor IA con prompt estructurado
│   ├── projection_service.py  # CRUD + auto-setup condicional
│   └── ...
│
├── config/
│   └── settings.py             # Variables Gemini + Proyecciones
│
├── utils/
│   ├── datetime_utils.py       # now_mazatlan(), today_mazatlan()
│   ├── permissions.py          # ensure_user_in_farm_or_admin()
│   └── db.py                   # get_db()
│
└── main.py                     # FastAPI app
```

---

**Siguiente paso**: Implementar módulo de Reforecast Automático con base en código anterior (adaptado a estructura actual).