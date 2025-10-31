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
│   ├── seeding.py         # Planes de siembra + sincronización fecha_inicio
│   ├── biometria.py       # Biometrías + SOB operativo + Reforecast
│   ├── harvest.py         # Olas y líneas de cosecha
│   ├── projections.py     # Proyecciones con Gemini AI
│   └── analytics.py       # ⭐ Dashboards y reportes
│
├── services/
│   ├── gemini_service.py          # Extractor IA (Excel/CSV/PDF/imágenes)
│   ├── projection_service.py      # Lógica de proyecciones + auto-setup
│   ├── reforecast_service.py      # ⭐ Reforecast automático (3 triggers)
│   ├── calculation_service.py     # ⭐ Cálculos matemáticos centralizados
│   ├── analytics_service.py       # ⭐ Agregación de datos para dashboards
│   ├── cycle_service.py
│   ├── seeding_service.py         # ⭐ Con sincronización de ciclo.fecha_inicio
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
| `Proyeccion` | `status` | `b`/`p`/`r`/`x` | Borrador / Publicada / Revisión / Cancelada |
| `Proyeccion` | `source_type` | `archivo`/`planes`/`reforecast` | Origen de la proyección |
| `CosechaOla` | `tipo` | `p`/`f` | Parcial / Final |
| `CosechaOla` | `status` | `p`/`r`/`x` | Pendiente / Realizada / Cancelada |
| `CosechaEstanque` | `status` | `p`/`c`/`x` | Pendiente / Confirmada / Cancelada |

---

## 🎯 Funcionalidades Core

### 1. Gestión de Granjas y Estanques
- CRUD completo con validación de superficie total
- Estanques con estados operativos y bandera `is_vigente`
- **Validación**: suma de estanques vigentes ≤ superficie total de granja

### 2. Ciclos de Producción
- **Restricción crítica**: 1 solo ciclo activo por granja
- Estados: `a` (activo) → `t` (terminado)
- Resumen automático al cerrar ciclo (SOB final, toneladas, kg/ha)
- **Creación con proyección opcional**: archivo procesado con Gemini
- **⭐ NUEVO**: `ciclo.fecha_inicio` se sincroniza automáticamente al confirmar última siembra

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
  ↓
⭐ Sincroniza ciclo.fecha_inicio con primera fecha de proyección
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
- **⭐ NUEVO**: Incluye semana 0 (edad_dias=0) obligatoriamente

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

**⭐ MEJORAS**: Ventana de siembras ajustada + Sincronización de fecha_inicio

**Reglas de Siembras**:
```python
NO existe plan              → ✅ Crear plan + siembras distribuidas
Plan en estado 'p'          → ✅ Actualizar plan + recrear siembras
Plan en estado 'e' o 'f'    → ❌ NO tocar (solo crea proyección)

# ⭐ NUEVO: Ventana de siembras ajustada
ventana_inicio = HOY (fecha actual en Mazatlán)
ventana_fin    = primera fecha de proyección
```

**Reglas de Cosechas**:
```python
NO existen olas             → ✅ Crear olas desde líneas con cosecha_flag
Olas en estado 'p'          → ✅ Recrear olas desde proyección
Olas en estado 'r'          → ❌ NO tocar (solo crea proyección)
```

**⭐ Sincronización Automática**:
```python
Al crear V1 de proyección:
  ciclo.fecha_inicio = primera_fecha_proyeccion

Al confirmar última siembra:
  ciclo.fecha_inicio = fecha_real_primera_siembra_confirmada
  plan.ventana_inicio = fecha_real_primera_siembra
  plan.ventana_fin = fecha_real_última_siembra
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
  → Crea ciclo + proyección V1 + auto-setup + sincroniza fecha_inicio
```

### 4. Siembras

#### Plan Único por Ciclo
- Estados: `p` (planeado) → `e` (ejecución) → `f` (finalizado)
- Auto-generación de siembras distribuidas uniformemente
- Overrides por estanque (densidad/talla)

#### Confirmación Automática ⭐
```python
Al confirmar siembra:
  - estanque.status = 'a' (activo)
  - siembra.fecha_siembra = HOY (Mazatlán)
  - plan.status = 'e' (primera siembra) o 'f' (última siembra)

Al confirmar ÚLTIMA siembra:
  - plan.ventana_inicio = fecha_primera_siembra_confirmada
  - plan.ventana_fin = fecha_última_siembra_confirmada
  - ciclo.fecha_inicio = fecha_primera_siembra_confirmada  ⭐ NUEVO
  - Trigger de Reforecast: Ajusta timeline completo de proyección
```

- Se fija `fecha_real`, `densidad_real`, `talla_real`
- Logs de reprogramación en `siembra_fecha_log`

### 5. Biometrías

#### Endpoint de Contexto (⭐ COMPLETO)
```
GET /biometria/cycles/{ciclo_id}/ponds/{estanque_id}/context
```
Retorna SOB operativo actual, datos de siembra, población estimada y valores proyectados. **Llamar antes de mostrar formulario de registro**.

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

- **Cambio**: `sob_usada_pct` ahora es **opcional**. Si `actualiza_sob_operativa=false`, backend usa SOB operativo actual automáticamente
- Registro en `sob_cambio_log` cuando actualiza SOB
- **Restricción**: Solo editable si NO actualizó SOB (auditoría)
- **⭐ Trigger de Reforecast**: Cada biometría registrada actualiza proyección automáticamente

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
- **⭐ Trigger de Reforecast**: Al confirmar/reprogramar cosecha

### 7. Reforecast Automático 🔮 (⭐ COMPLETO)

Sistema que actualiza automáticamente el borrador de proyección cuando ocurren eventos operativos.

#### Triggers Implementados

**✅ TRIGGER 1: Biometrías** (PROBADO)
```python
# Anclaje de datos reales
Biometría → Agregación ponderada por población
         → Ancla PP y SOB en semana más cercana
         → Recalcula SOB final objetivo
         → Interpola series con curvas suaves
```

**Características**:
- Agregación ponderada: `PP_granja = Σ(PP_estanque × org_estimados) / Σ(org_estimados)`
- Ventana de agregación: Fin de semana (Sáb-Dom) o ±N días configurable
- Validación de cobertura mínima (30%, mín 3 estanques)
- Modo "soft": No sobrescribe borradores manuales

**✅ TRIGGER 2: Siembras** (⭐ ACTUALIZADO)
```python
# Shift de timeline completa + Sincronización
Al confirmar ÚLTIMA siembra del plan:
  1. Calcula desvío real vs tentativo
  2. Ajusta todas las fechas de proyección
  3. Actualiza ventanas del plan (inicio, fin)
  4. ⭐ Sincroniza ciclo.fecha_inicio con primera siembra real
```

**Características**:
- Solo se ejecuta cuando se confirma la **última siembra** del plan
- Usa fecha real de última siembra confirmada
- Mantiene anclajes de biometrías previas
- **⭐ NUEVO**: Sincroniza `ciclo.fecha_inicio` con realidad operativa

**✅ TRIGGER 3: Cosechas** (IMPLEMENTADO)
```python
# Ajuste de retiros y SOB futuro
Cosecha confirmada → Actualiza retiro en línea de proyección
                  → Recalcula SOB desde cosecha hacia adelante
                  → SOB_después = SOB_antes × (1 - retiro/densidad_base)
```

#### Características Técnicas

**Interpolación con Curvas**:
- PP: S-curve (crecimiento sigmoidea)
- SOB: Linear (mortalidad gradual) + FORZADO de valor final objetivo
- Anclajes fijos: Semanas con datos reales

**Agregación Ponderada**:
```python
# Peso por población estimada
org_estimados = (densidad_base - retiros) × area × (SOB/100)

# PP ponderado
PP_granja = Σ(PP_estanque × org_estimados) / Σ(org_estimados)

# SOB ponderado  
SOB_granja = Σ(SOB_estanque × peso_base) / Σ(peso_base)
```

**Gestión de Borrador**:
```python
# Borrador único de reforecast por ciclo
1. Si existe borrador reforecast → reutilizar
2. Si existe borrador manual:
   - Modo soft → skip
   - Modo strict → error 409
3. Si no hay borrador → clonar proyección actual
```

#### Configuración

```python
# config/settings.py
REFORECAST_ENABLED: bool = True           # Master switch
REFORECAST_MIN_COVERAGE_PCT: float = 30.0 # % mínimo de estanques
REFORECAST_MIN_PONDS: int = 3             # Mínimo absoluto
REFORECAST_WEEKEND_MODE: bool = False     # True = Sáb-Dom
REFORECAST_WINDOW_DAYS: int = 0           # Si weekend_mode=False
```

#### Estructura de Respuesta

```python
{
  "skipped": False,
  "proyeccion_id": 123,
  "week_idx": 8,
  "anchored": {
    "pp": True,
    "sob": True,
    "anchor_date": "2025-03-15"
  },
  "agg": {
    "pp": 12.45,
    "sob": 85.30,
    "coverage_pct": 75.0,
    "measured_ponds": 6,
    "total_ponds": 8
  },
  "lines_updated": 20,
  "sob_final_objetivo_pct": 83.5
}
```

### 8. Analytics y Dashboards 📊 (⭐ IMPLEMENTADO)

#### Calculation Service
**Centralización de lógica matemática** - Sin endpoints propios, consumido por otros servicios.

**Funciones implementadas**:
```python
# Cálculos básicos por estanque
calculate_densidad_viva()      # Densidad efectiva (base - retiros) × SOB
calculate_org_vivos()          # Organismos totales = densidad × área
calculate_biomasa_kg()         # Biomasa = org_vivos × (pp_g / 1000)

# Agregaciones ponderadas (⭐ MEJORADAS)
calculate_weighted_density()   # Densidad promedio ponderada por superficie
calculate_weighted_pp()        # ⭐ PP promedio ponderado por población (mini-fix)
calculate_global_sob()         # ⭐ SOB global correcto (reconstruye remanente pre-SOB)
calculate_total_biomass()      # Suma total de biomasa

# Análisis y comparativas
calculate_deviation_pct()      # Desviación % vs proyección
calculate_growth_rate()        # Tasa de crecimiento (g/semana)
```

**⭐ MEJORAS CRÍTICAS**:
1. **`calculate_global_sob()`**: Reconstruye correctamente el remanente pre-SOB
   ```python
   # ANTES (incorrecto):
   SOB_global = Σ org_vivos / Σ(densidad_base × área)  # ❌ Ignora retiros
   
   # AHORA (correcto):
   densidad_remanente = densidad_viva / (SOB% / 100)  # Reconstruye pre-SOB
   SOB_global = Σ org_vivos / Σ(densidad_remanente × área)  # ✅
   ```

2. **`calculate_weighted_pp()`**: Mini-fix para manejo correcto de nulls
   ```python
   # ANTES: Incluía estanques sin PP (contribuían 0)
   # AHORA: Solo pondera estanques que TIENEN pp_vigente_g
   ```

#### Analytics Service
**Preparación de datos para dashboards** - Consumido por `api/analytics`.

**⭐ REGLAS IMPLEMENTADAS**:
```python
# 1. Solo estanques con siembra confirmada
_get_densidad_base() → requiere siembra.status='f'
_build_pond_snapshot() → retorna None si no hay siembra confirmada

# 2. Fuentes de datos explícitas
pp_fuente: "biometria" | "proyeccion" | "plan_inicial"
sob_fuente: "operativa_actual" | "proyeccion" | "default_inicial"
pp_updated_at: datetime | None  # Timestamp de última actualización

# 3. Prioridades de datos
SOB operativo:
  1. Último log operativo (más reciente)
  2. Proyección actual (línea cercana a hoy)
  3. 100% (default inicial)

PP vigente:
  1. Última biometría (más reciente)
  2. Proyección actual (línea cercana a hoy)
  3. Talla inicial del plan

# 4. Sample sizes (metadata)
{
  "sample_sizes": {
    "ponds_total": 10,
    "ponds_with_density": 8,
    "ponds_with_org_vivos": 8
  }
}

# 5. Solo proyecciones publicadas (is_current=True, status='p')
```

**Funciones principales**:
```python
get_cycle_overview()      # Dashboard general del ciclo
get_pond_detail()         # Detalle individual de estanque
get_growth_curve_data()   # Serie temporal PP (real vs proyectado)
get_biomass_evolution_data()   # Biomasa acumulada
get_density_evolution_data()   # Densidad promedio decreciente
```

**Características**:
- Agregación ponderada por población viva
- SOB global (vivos totales / remanente total)
- Próximas operaciones (90 días para cosechas)
- Alertas operativas (biometrías atrasadas, desvíos)

#### API Endpoints

```python
GET /analytics/cycles/{ciclo_id}/overview
# Retorna:
# - KPIs: biomasa, densidad, SOB, PP (con sample_sizes)
# - Estados: activos, en siembra, en cosecha, finalizados
# - Gráficas: crecimiento, biomasa, densidad
# - Próximas operaciones: siembras, cosechas
# - Detalle por estanque (con fuentes de datos)

GET /analytics/ponds/{estanque_id}/detail?ciclo_id={ciclo_id}
# Retorna:
# - KPIs: biomasa, densidad, org_vivos, PP, SOB (con fuentes)
# - Gráficas: crecimiento, densidad del estanque
# - Detalles: área, densidad inicial, días cultivo, tasa crecimiento
```

---

## 📌 API Endpoints

### Autenticación
```
POST   /auth/register              # Registro de usuario
POST   /auth/token                 # Login (retorna JWT)
GET    /auth/me                    # Usuario actual
```

### Granjas
```
POST   /farms                      # Crear granja
GET    /farms                      # Listar granjas del usuario
PATCH  /farms/{id}                 # Actualizar granja
```

### Estanques
```
POST   /ponds/farms/{granja_id}   # Crear estanque
GET    /ponds/farms/{granja_id}   # Listar estanques
GET    /ponds/{id}                 # Detalle de estanque
PATCH  /ponds/{id}                 # Actualizar estanque
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
POST   /seeding/seedings/{id}/confirm           # ⭐ Confirmar siembra (+ sync fecha_inicio)
POST   /seeding/seedings/{id}/reprogram         # Reprogramar
POST   /seeding/seedings/{id}/logs              # Logs de cambios
GET    /seeding/plans/{plan_id}/status          # Status del plan
DELETE /seeding/plans/{plan_id}                 # Eliminar plan
```

### Biometrías
```
GET    /biometria/cycles/{ciclo_id}/ponds/{estanque_id}/context  # ⭐ Contexto para registro
POST   /biometria/cycles/{ciclo_id}/ponds/{estanque_id}          # Registrar + Reforecast
GET    /biometria/cycles/{ciclo_id}/ponds/{estanque_id}          # Listar por estanque
GET    /biometria/cycles/{ciclo_id}                              # Listar por ciclo
GET    /biometria/{biometria_id}                                 # Detalle
PATCH  /biometria/{biometria_id}                                 # Actualizar
DELETE /biometria/{biometria_id}                                 # Eliminar
```

### Cosechas
```
POST   /harvest/cycles/{ciclo_id}/waves         # Crear ola + líneas
GET    /harvest/cycles/{ciclo_id}/waves         # Listar olas
GET    /harvest/waves/{wave_id}                 # Detalle de ola
POST   /harvest/waves/{wave_id}/cancel          # Cancelar ola
POST   /harvest/harvests/{id}/reprogram         # Reprogramar línea
POST   /harvest/harvests/{id}/confirm           # Confirmar cosecha
```

### Analytics ⭐ IMPLEMENTADO
```
GET    /analytics/cycles/{ciclo_id}/overview    # Dashboard general del ciclo
GET    /analytics/ponds/{estanque_id}/detail    # Dashboard detallado de estanque
```

---

## 🧮 Zona Horaria

**Unificada**: `America/Mazatlan` (UTC-7)

```python
# utils/datetime_utils.py

def now_mazatlan() -> datetime:
    """Retorna datetime naive en zona Mazatlán"""
    return datetime.now(MAZATLAN_TZ).replace(tzinfo=None)

def today_mazatlan() -> date:
    """Retorna date en zona Mazatlán"""
    return now_mazatlan().date()

def to_mazatlan_naive(dt: datetime) -> datetime:
    """Normaliza datetime a Mazatlán naive para persistencia"""
    if dt.tzinfo is None:
        return dt.replace(microsecond=0)
    return dt.astimezone(MAZATLAN_TZ).replace(tzinfo=None, microsecond=0)
```

**Uso**:
- Todas las fechas de servidor (biometrías, logs)
- Timestamps `created_at`, `updated_at`
- MySQL almacena como DATETIME sin zona (naive)
- **⭐ USADO EN**: Analytics, Siembras, Biometrías, Reforecast

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
GEMINI_MODEL_ID=models/gemini-2.5-flash
GEMINI_VISION_MODEL_ID=models/gemini-2.5-pro
GEMINI_TIMEOUT_MS=120000

# Proyecciones
MAX_PROJECTION_ROWS=200
PROJECTION_EXTRACTOR=gemini

# Reforecast Automático
REFORECAST_ENABLED=True
REFORECAST_MIN_COVERAGE_PCT=30.0
REFORECAST_MIN_PONDS=3
REFORECAST_WEEKEND_MODE=False
REFORECAST_WINDOW_DAYS=0
```

---

## 📏 Reglas de Negocio

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

### ⭐ Reglas de Overrides en Densidad/Talla
```python
# Siempre prioridad: override > plan
if override > 0:
    usar override
else:
    usar plan

# ⚠️ IMPORTANTE: override = 0 significa "usar plan", NO cero literal
densidad_override_org_m2 = 0  → usa plan.densidad_org_m2
densidad_override_org_m2 = None → usa plan.densidad_org_m2
densidad_override_org_m2 = 10.5 → usa 10.5 (override)
```

### ⭐ Sincronización de Fecha de Inicio
```python
# MOMENTO 1: Al crear V1 de proyección
ciclo.fecha_inicio = primera_fecha_proyeccion

# MOMENTO 2: Al confirmar última siembra
ciclo.fecha_inicio = fecha_primera_siembra_confirmada  # Fecha real operativa
plan.ventana_inicio = fecha_primera_siembra_confirmada
plan.ventana_fin = fecha_última_siembra_confirmada

# EFECTO: Analytics usa la edad correcta del ciclo
dias_ciclo = (HOY - ciclo.fecha_inicio).days
```

---

## 🚀 Estado Actual

**✅ Completado**:
- Autenticación JWT
- CRUD Granjas + Estanques
- Gestión de Ciclos
- Sistema de Siembras **⭐ CON sincronización de fecha_inicio**
- Biometrías con SOB operativo + endpoint de contexto
- Cosechas (olas + líneas + cancelación masiva)
- Proyecciones con Gemini AI
- Auto-setup condicional **⭐ CON ventana ajustada [HOY, primera_fecha_proyección]**
- Versionamiento inteligente
- **⭐ Reforecast automático (COMPLETO)**:
  - ✅ Trigger de biometrías (probado)
  - ✅ Trigger de siembras (probado + sincronización)
  - ✅ Trigger de cosechas (implementado)
  - ✅ Interpolación con forzado de SOB final
  - ✅ Agregación ponderada mejorada
- Logs de auditoría
- Validaciones pond-first
- Zona horaria unificada
- **⭐ Módulo Analytics (COMPLETO)**:
  - ✅ `calculation_service.py` - Lógica matemática centralizada (con mejoras críticas)
  - ✅ `analytics_service.py` - Agregación de datos (con reglas estrictas)
  - ✅ `api/analytics.py` - 2 endpoints operativos
  - ✅ Filtrado estricto (solo siembras confirmadas)
  - ✅ Fuentes de datos explícitas
  - ✅ Sample sizes en KPIs

**🚧 Pendiente**:
- Endpoints adicionales de analytics (comparativas históricas, proyección de cosecha)
- Sistema de roles avanzado
- Módulo de Alimentación (FCR, consumo diario)

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
- Modelos: `gemini-2.5-flash` (texto), `gemini-2.5-pro` (vision)

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

## 📊 Métricas del Proyecto

```
📦 Módulos implementados:     12/12 (100%) ⭐
📋 Líneas de código:          ~10,000+
🗄️ Tablas BD:                 20
📌 Endpoints:                 60+
🤖 Integración IA:            Google Gemini API v1
🔮 Reforecast:                3/3 triggers implementados ✅
📊 Analytics:                 2 endpoints operativos + servicios completos ✅
🧮 Calculation Service:       15+ funciones matemáticas
🎯 Coverage:                  Siembras confirmadas, fuentes explícitas
```

---

## 📁 Estructura de Archivos Clave

```
AquaTrack/
├── models/
│   ├── projection.py           # Proyeccion + ProyeccionLinea + SourceType
│   ├── biometria.py           # Biometria + SOBCambioLog + SOBFuente
│   ├── cycle.py               # Ciclo + CicloResumen
│   ├── seeding.py             # SiembraPlan + SiembraEstanque + logs
│   └── ...
│
├── schemas/
│   ├── projection.py           # CanonicalProjection + DTOs
│   ├── biometria.py           # BiometriaCreate + BiometriaContextOut
│   ├── cycle.py               # CycleCreate (con validación fechas futuras)
│   └── ...
│
├── services/
│   ├── gemini_service.py       # Extractor IA con prompt estructurado
│   ├── projection_service.py   # CRUD + auto-setup + sincronización
│   ├── reforecast_service.py   # ⭐ 3 triggers completos + interpolación
│   ├── seeding_service.py      # ⭐ Con _sync_cycle_fecha_inicio()
│   ├── biometria_service.py    # Gestión biometrías + SOB + contexto
│   ├── calculation_service.py  # ⭐ Cálculos puros (mejoras críticas)
│   ├── analytics_service.py    # ⭐ Agregación (reglas estrictas)
│   └── ...
│
├── api/
│   ├── cycles.py               # ⭐ Label mejorado "Primera siembra planificada"
│   ├── analytics.py            # ⭐ 2 endpoints dashboards
│   └── ...
│
├── config/
│   └── settings.py             # Variables Gemini + Proyecciones + Reforecast
│
├── utils/
│   ├── datetime_utils.py       # ⭐ now_mazatlan(), today_mazatlan(), to_mazatlan_naive()
│   ├── permissions.py          # ensure_user_in_farm_or_admin()
│   └── db.py                   # get_db()
│
└── main.py                     # FastAPI app
```

---

## 🎯 Próximos Pasos

### Prioridad Crítica 🔴
1. **Testing de Reforecast**: Validar trigger de cosechas en entorno real
2. **Validación de Imports**: Verificar nombres de modelos en `analytics_service.py`
3. **Testing de Analytics**: Probar endpoints con datos reales en ciclo completo

### Prioridad Alta 🟡
1. **Sistema de Permisos Granulares**:
   - Permisos por operación (crear/editar/eliminar)
   - Roles personalizados por granja
   - Separación: Admin Granja vs Operador vs Lector
   - Middleware de autorización por endpoint
   
2. **Expandir Analytics**: 
   - Comparativas históricas ciclo vs ciclo
   - Proyección de cosecha (fecha óptima, biomasa estimada)
   - Alertas operativas avanzadas (biometrías atrasadas, desvíos críticos)

### Prioridad Media 🟢
1. **Notificaciones**: 
   - Alertas push para eventos críticos
   - Recordatorios de operaciones pendientes
   - Resúmenes diarios/semanales

2. **Reportes PDF**: 
   - Generación automática de informes de ciclo
   - Exportación de datos históricos
   - Dashboards imprimibles

### Prioridad Baja ⚪ (Post-entrega)
1. **Módulo de Alimentación** (Opcional para V2): 
   - Registro de alimentación diaria
   - Cálculo de FCR real
   - Optimización de consumo
   - Proyección de costos operativos

---

## 🎯 Checklist para Primera Entrega

- [x] ✅ Autenticación JWT
- [x] ✅ CRUD Granjas + Estanques
- [x] ✅ Gestión de Ciclos completa
- [x] ✅ Proyecciones con Gemini AI
- [x] ✅ Auto-setup inteligente
- [x] ✅ Sistema de Siembras
- [x] ✅ Biometrías + SOB operativo
- [x] ✅ Cosechas (olas + líneas)
- [x] ✅ Reforecast automático (3 triggers)
- [x] ✅ Analytics (dashboards)
- [ ] 🚧 **Sistema de permisos granulares**
- [ ] 🚧 **Testing completo de flujos**
- [ ] 🚧 **Validación de imports/modelos**
- [ ] ⏸️ Notificaciones (opcional)
- [ ] ⏸️ Reportes PDF (opcional)
- [ ] ❌ Módulo de Alimentación (V2)

---

## 🐛 Notas de Implementación

### ⚠️ Puntos Críticos a Verificar

#### 1. Nombres de Modelos en Analytics
```python
# Archivo: services/analytics_service.py
# VERIFICAR que los imports coincidan con tu estructura:

from models.user import Usuario        # ¿O es models.usuario?
from models.cycle import Ciclo         # ¿O es models.ciclo?
from models.pond import Estanque       # ¿O es models.estanque?
from models.biometria import Biometria, SOBCambioLog
from models.seeding import SiembraPlan, SiembraEstanque
from models.harvest import CosechaOla, CosechaEstanque
from models.projection import Proyeccion, ProyeccionLinea
```

#### 2. Estructura de SOBCambioLog
```python
# VERIFICAR que existe el modelo:
from models.biometria import SOBCambioLog

# Y que tiene estos campos:
SOBCambioLog.changed_at
SOBCambioLog.sob_nueva_pct
```

#### 3. Zona Horaria en Analytics
```python
# VERIFICAR que se usa consistently:
from utils.datetime_utils import today_mazatlan, now_mazatlan

# En lugar de:
from datetime import date
today = date.today()  # ❌ Puede ser UTC del servidor
```

### ✅ Mejoras Implementadas

#### Calculation Service
1. **`calculate_global_sob()`**: Reconstrucción correcta del remanente pre-SOB
2. **`calculate_weighted_pp()`**: Mini-fix para nulls (solo estanques con PP)

#### Analytics Service
1. **Filtrado estricto**: Solo estanques con `siembra.status='f'`
2. **Fuentes explícitas**: `pp_fuente`, `sob_fuente`, `pp_updated_at`
3. **Sample sizes**: Metadata de cobertura en KPIs
4. **Solo publicadas**: Usa solo `proyeccion.is_current=True, status='p'`

#### Seeding Service
1. **`_sync_cycle_fecha_inicio()`**: Nueva función para sincronizar fecha_inicio
2. **`_update_plan_windows()`**: Actualiza ventanas con fechas reales
3. **`confirm_seeding()`**: Ejecuta ambas funciones al finalizar plan

#### Projection Service
1. **`_auto_setup_seeding()`**: Ventana ajustada `[HOY, primera_fecha_proyección]`
2. **`create_projection_from_file()`**: Sincroniza `ciclo.fecha_inicio` en V1

#### Reforecast Service
1. **`_force_last_value_and_interpolate()`**: Fuerza SOB final objetivo
2. **`calc_sob_final_objetivo()`**: Recalcula objetivo ajustado por observaciones
3. **`trigger_siembra_reforecast()`**: Sincroniza con fecha real de última siembra

---

## 📖 Glosario

| Término | Significado |
|---------|-------------|
| **PP** | Peso Promedio (g) |
| **SOB** | Supervivencia Operacional de Base (%) |
| **FCR** | Feed Conversion Ratio (kg alimento / kg biomasa) |
| **Org/m²** | Organismos por metro cuadrado |
| **Reforecast** | Actualización automática de proyección con datos reales |
| **Anclaje** | Punto fijo en proyección basado en datos reales |
| **Interpolación** | Cálculo de valores intermedios entre anclajes |
| **Agregación ponderada** | Promedio considerando peso/importancia de cada estanque |

---

## 🤝 Contribución

Este proyecto sigue una arquitectura limpia con separación de responsabilidades:

- **Models**: Definición de tablas (SQLAlchemy ORM)
- **Schemas**: Validación de entrada/salida (Pydantic)
- **Services**: Lógica de negocio pura
- **API**: Controllers (thin layer)
- **Utils**: Helpers reutilizables

**Convenciones**:
- Snake_case para Python
- Comentarios en español
- Docstrings en español
- Type hints obligatorios
- Logs en español

---

## 📝 Licencia

Proyecto privado - Todos los derechos reservados.

---

**Contexto para IA**: Este sistema gestiona ciclos completos de producción de camarón. Los usuarios crean granjas con estanques, inician ciclos, cargan proyecciones (manualmente o con IA desde archivos), planifican siembras, registran biometrías y ejecutan cosechas. El reforecast automático ajusta las proyecciones en tiempo real conforme se registran datos operativos. El módulo de analytics prepara datos agregados para dashboards visuales con KPIs, gráficas y alertas. Toda la lógica de negocio respeta estados estrictos y audita cambios críticos. **La sincronización de `ciclo.fecha_inicio` garantiza que la edad del ciclo sea siempre precisa, mejorando la exactitud de los cálculos de analytics**.