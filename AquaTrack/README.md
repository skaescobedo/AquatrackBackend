# 🐟 AquaTrack API

> Sistema integral de gestión acuícola con proyecciones inteligentes, reforecast en tiempo real y análisis pond-first para optimización de ciclos productivos.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479A1?style=flat&logo=mysql&logoColor=white)](https://mysql.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 Tabla de Contenidos

- [Descripción](#-descripción)
- [Características Principales](#-características-principales)
- [Arquitectura](#-arquitectura)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Endpoints Disponibles](#-endpoints-disponibles)
- [Modelos de Datos](#-modelos-de-datos)
- [Flujo Operativo](#-flujo-operativo)
- [Sistema de Proyecciones](#-sistema-de-proyecciones)
- [Cálculos Pond-First](#-cálculos-pond-first)
- [Roadmap](#-roadmap)

---

## 🎯 Descripción

**AquaTrack** es una API REST construida con **FastAPI** para la gestión integral de operaciones acuícolas. El sistema implementa un enfoque **pond-first** donde cada estanque es la unidad básica de cálculo, agregándose posteriormente a nivel de granja/ciclo para generar métricas consolidadas.

### **Problema que resuelve**

Las granjas acuícolas enfrentan:
- ❌ Desviaciones entre proyecciones y resultados reales
- ❌ Falta de trazabilidad en cambios de SOB (supervivencia)
- ❌ Dificultad para comparar rendimiento Real vs Proyectado
- ❌ Reprogramaciones sin auditoría
- ❌ Datos dispersos entre estanques

### **Solución AquaTrack**

- ✅ **Proyecciones con IA**: Ingesta de archivos (Excel/CSV/PDF) vía Gemini para generar proyecciones automáticas
- ✅ **Reforecast vivo**: Recalibración automática V+1 en borrador al confirmar siembras, biometrías o cosechas
- ✅ **Auditoría completa**: Logs de cambios de fechas (siembra/cosecha) y SOB (supervivencia)
- ✅ **Comparativos Real vs Proyección**: Cálculos agregados desde estanques hacia granja
- ✅ **Sistema pond-first**: Cada estanque tiene su estado operativo, biomasa, densidad y PP propios

---

## ✨ Características Principales

### **1. Gestión de Granjas y Estanques**
- CRUD completo de granjas con validación de superficie total
- Estanques con estados operativos (`i`/`a`/`c`/`m`) y bandera `is_vigente`
- Validación: suma de estanques vigentes ≤ superficie total de granja

### **2. Ciclos de Producción**
- **Restricción crítica**: 1 solo ciclo activo por granja
- Estados: `a` (activo) → `t` (terminado)
- Resumen automático al cerrar ciclo (SOB final, toneladas, kg/ha)

### **3. Siembras**
- **Plan único por ciclo** con estados: `p` (planeado) → `e` (ejecución) → `f` (finalizado)
- Auto-generación de siembras distribuidas uniformemente en ventana de fechas
- Overrides por estanque (densidad/talla)
- **Confirmación automática**: al confirmar siembra, el estanque pasa a `status='a'` (activo)
- Logs de reprogramación (`siembra_fecha_log`)

### **4. Biometrías**
- **Fecha fijada por servidor** en zona horaria `America/Mazatlan` (naive para MySQL)
- Cálculo automático de PP (peso promedio) e incremento semanal
- **Sistema de SOB operativo**:
  - Al sembrar: SOB base = 100% automático
  - Primera biometría: puede usar 100% inicial o actualizarlo
  - Biometrías posteriores: solo actualizan si hay cambios reales
- Registro en `sob_cambio_log` cuando `actualiza_sob_operativa=True`
- **Restricción**: solo editable si NO actualizó SOB (para auditoría)

### **5. Cosechas**
- **Olas de cosecha** por ciclo (sin plan maestro):
  - Tipo: `p` (parcial) o `f` (final)
  - Auto-generación de líneas para todos los estanques del plan de siembra
- **Confirmación inteligente**:
  - Obtiene PP de última biometría automáticamente
  - Si provees `biomasa_kg` → deriva `densidad_retirada_org_m2`
  - Si provees `densidad_retirada_org_m2` → deriva `biomasa_kg`
  - Fórmulas:
    - `densidad = (biomasa_kg * 1000) / (pp_g * area_m2)`
    - `biomasa = (densidad * area_m2 * pp_g) / 1000`
- Logs de reprogramación (`cosecha_fecha_log`)
- **Cancelación masiva de olas**: marca ola como `'x'` y cancela todas las líneas pendientes

### **6. Proyecciones con IA (Gemini)** 🤖
- **Ingesta desde archivo**: Sube Excel/CSV/PDF al crear proyección
  - Gemini interpreta el archivo y genera JSON con:
    - Serie semanal de PP proyectado
    - SOB proyectado por semana
    - Fechas de hitos (siembras, cosechas)
- **Generación automática**:
  - Plan de siembras desde proyección publicada
  - Olas de cosecha según fechas proyectadas
- **Estados de proyección**:
  - `b` (borrador editable)
  - `p` (publicada congelada)
  - `r` (reforecast - marcador de origen)
  - `x` (anulada)
- **Restricciones**:
  - Solo **1 proyección publicada** (`is_current=1`) por ciclo
  - Solo **1 borrador** (`status='b'`) por ciclo
  - La V1 se autopublica al crear

### **7. Reforecast Vivo** 📊
- **Disparadores automáticos**:
  - ✅ Confirmación de siembra
  - ✅ Registro de biometría relevante
  - ✅ Cambio de SOB (`sob_cambio_log`)
  - ✅ Confirmación de cosecha (parcial/final)
  - ✅ Reprogramación de fechas (siembra/cosecha)
- **Comportamiento**:
  - Si no existe borrador V+1 → **crear**
  - Si ya existe V+1 → **actualizar**
  - Al publicar → pasa a `status='p'`, `is_current=1` y se congela
- **Ajustes automáticos**:
  - Recalibra PP proyectado según tendencia observada
  - Ajusta SOB proyectado hacia SOB operativo agregado
  - Recomputa población/biomasa proyectada

### **8. Sistema de Auditoría**
- **Logs de cambios de fecha**:
  - `siembra_fecha_log`: historial de reprogramaciones de siembras
  - `cosecha_fecha_log`: historial de reprogramaciones de cosechas
- **Logs de cambios de SOB**:
  - `sob_cambio_log`: rastrea origen (`operativa_actual`, `ajuste_manual`, `reforecast`)
- **Usuario y timestamp** en todas las confirmaciones
- **Política de no borrado**: todo se desactiva (`is_vigente=0`, `status='x'`) o se cierra

---

## 🏗️ Arquitectura

### **Stack Tecnológico**

```
┌─────────────────────────────────────────┐
│           FastAPI mas actual                │
│     (Python 3.12 + Pydantic mas actual)         │
├─────────────────────────────────────────┤
│         SQLAlchemy 2.0 ORM              │
├─────────────────────────────────────────┤
│           MySQL 8.0+                     │
│      (utf8mb4_unicode_ci)               │
├─────────────────────────────────────────┤
│       Gemini API (google-genai)         │
│    (Ingesta de archivos → JSON)         │
└─────────────────────────────────────────┘
```

### **Patrón de Diseño**

```
┌──────────────┐
│   Routers    │  ← Endpoints REST (api/)
└──────┬───────┘
       │
┌──────▼───────┐
│   Schemas    │  ← DTOs Pydantic (schemas/)
└──────┬───────┘
       │
┌──────▼───────┐
│   Services   │  ← Lógica de negocio (services/)
└──────┬───────┘
       │
┌──────▼───────┐
│    Models    │  ← SQLAlchemy (models/)
└──────────────┘
```

### **Filosofía Pond-First**

```
Estanque 1 (real) ─┐
Estanque 2 (real) ─┼──> Agregación ponderada ──> KPIs Granja
Estanque 3 (real) ─┘         (biomasa, PP, SOB)
                    
Proyección (granja) ──────────────────────> Comparativo Real vs Proy
```

---

## 📦 Instalación

### **Requisitos Previos**

- Python 3.12+
- MySQL 8.0+
- pip (gestor de paquetes)

### **Paso 1: Clonar repositorio**

```bash
git clone https://github.com/tu-usuario/aquatrack-backend.git
cd aquatrack-backend/AquaTrack
```

### **Paso 2: Crear entorno virtual**

```bash
python -m venv .venv
```

### **Paso 3: Activar entorno**

**Windows:**
```bash
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
source .venv/bin/activate
```

### **Paso 4: Instalar dependencias**

```bash
pip install -r requirements.txt
```

### **Paso 5: Crear base de datos**

```sql
CREATE DATABASE aquatrack_bd CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Ejecutar los scripts SQL proporcionados en `/docs/database/` para crear las tablas.

### **Paso 6: Configurar variables de entorno**

Crear archivo `.env` en la raíz del proyecto:

```env
DATABASE_URL=mysql+pymysql://root:tu_password@localhost:3306/aquatrack_bd
SECRET_KEY=tu_secret_key_super_seguro_cambialo
ACCESS_TOKEN_EXPIRE_MINUTES=720
ALGORITHM=HS256

CORS_ALLOW_ORIGINS=["http://localhost:4200"]

# Gemini API (para proyecciones)
GEMINI_API_KEY=tu_api_key_de_google
```

### **Paso 7: Iniciar servidor**

```bash
uvicorn main:app --reload
```

La API estará disponible en: **http://localhost:8000**

Documentación interactiva: **http://localhost:8000/docs**

---

## ⚙️ Configuración

### **Variables de Entorno**

| Variable | Descripción | Default |
|----------|-------------|---------|
| `DATABASE_URL` | URL de conexión MySQL | `mysql+pymysql://root:password@localhost:3306/aquatrack` |
| `SECRET_KEY` | Clave para JWT | `CHANGE_ME` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración de tokens | `720` (12h) |
| `CORS_ALLOW_ORIGINS` | Orígenes permitidos | `["http://localhost:4200"]` |
| `GEMINI_API_KEY` | API Key de Google Gemini | `None` |

### **Zona Horaria**

Todas las fechas naive se interpretan como **America/Mazatlan** (implementación centralizada en `utils/datetime_utils.py`).

---

## 📁 Estructura del Proyecto

```
AquaTrack/
│
├── main.py                 # Entry point FastAPI
├── .env                    # Variables de entorno (git-ignored)
├── requirements.txt        # Dependencias Python
│
├── api/                    # 🌐 Routers (Endpoints REST)
│   ├── auth.py            # Login, registro, /me
│   ├── farms.py           # CRUD granjas
│   ├── ponds.py           # CRUD estanques
│   ├── cycles.py          # Gestión ciclos
│   ├── seeding.py         # Siembras y plan
│   ├── biometria.py       # Biometrías
│   ├── harvest.py         # Cosechas (olas + líneas)
│   └── router.py          # Router principal
│
├── config/
│   └── settings.py        # Configuración Pydantic
│
├── models/                # 🗄️ SQLAlchemy Models
│   ├── user.py           # Usuario + UsuarioGranja
│   ├── role.py           # Rol
│   ├── farm.py           # Granja
│   ├── pond.py           # Estanque
│   ├── cycle.py          # Ciclo + CicloResumen
│   ├── seeding.py        # SiembraPlan + SiembraEstanque + SiembraFechaLog
│   ├── biometria.py      # Biometria + SOBCambioLog
│   ├── harvest.py        # CosechaOla + CosechaEstanque + CosechaFechaLog
│   └── __init__.py
│
├── schemas/               # 📋 Pydantic Schemas (DTOs)
│   ├── user.py
│   ├── farm.py
│   ├── pond.py
│   ├── cycle.py
│   ├── seeding.py
│   ├── biometria.py
│   ├── harvest.py
│   └── __init__.py
│
├── services/              # 🔧 Lógica de negocio
│   ├── auth_service.py
│   ├── farm_service.py
│   ├── pond_service.py
│   ├── cycle_service.py
│   ├── seeding_service.py
│   ├── biometria_service.py
│   ├── harvest_service.py
│   └── __init__.py
│
└── utils/                 # 🛠️ Utilidades
    ├── db.py             # Conexión SQLAlchemy
    ├── security.py       # JWT, bcrypt
    ├── dependencies.py   # get_current_user
    ├── permissions.py    # Validación permisos por granja
    ├── datetime_utils.py # Manejo de fechas (Mazatlán)
    └── __init__.py
```

---

## 🔌 Endpoints Disponibles

### **🔐 Autenticación**

```http
POST   /auth/token        # Login (OAuth2PasswordRequestForm)
POST   /auth/register     # Registro de usuario
GET    /auth/me           # Usuario actual
```

### **🏢 Granjas**

```http
GET    /farms             # Listar granjas
POST   /farms             # Crear granja (admin only)
PUT    /farms/{id}        # Actualizar granja (admin only)
```

### **🏊 Estanques**

```http
POST   /ponds/farms/{granja_id}     # Crear estanque
GET    /ponds/farms/{granja_id}     # Listar estanques de granja
GET    /ponds/{estanque_id}         # Detalle de estanque
PATCH  /ponds/{estanque_id}         # Actualizar estanque
```

### **🔄 Ciclos**

```http
POST   /cycles/farms/{granja_id}           # Crear ciclo
GET    /cycles/farms/{granja_id}/active    # Ciclo activo
GET    /cycles/farms/{granja_id}           # Listar ciclos
GET    /cycles/{ciclo_id}                  # Detalle ciclo
PATCH  /cycles/{ciclo_id}                  # Actualizar ciclo
POST   /cycles/{ciclo_id}/close            # Cerrar ciclo
GET    /cycles/{ciclo_id}/resumen          # Resumen (si cerrado)
```

### **🌱 Siembras**

```http
POST   /seeding/cycles/{ciclo_id}/plan                  # Crear plan (auto-siembras)
GET    /seeding/cycles/{ciclo_id}/plan                  # Ver plan + siembras
POST   /seeding/plan/{plan_id}/ponds/{estanque_id}     # Agregar siembra manual
POST   /seeding/seedings/{siembra_id}/reprogram        # Reprogramar (fecha/densidad/talla/lote)
POST   /seeding/seedings/{siembra_id}/confirm          # Confirmar siembra
DELETE /seeding/plan/{plan_id}                         # Eliminar plan (si no hay confirmadas)
```

### **📊 Biometrías**

```http
POST   /biometria/cycles/{ciclo_id}/ponds/{estanque_id}   # Registrar biometría
GET    /biometria/cycles/{ciclo_id}/ponds/{estanque_id}   # Historial
GET    /biometria/{biometria_id}                          # Detalle
PATCH  /biometria/{biometria_id}                          # Actualizar (solo notas)
```

### **🎣 Cosechas**

```http
POST   /harvest/cycles/{ciclo_id}/wave               # Crear ola (auto-líneas)
GET    /harvest/cycles/{ciclo_id}/waves              # Listar olas
GET    /harvest/waves/{ola_id}                       # Detalle ola + líneas
POST   /harvest/waves/{ola_id}/cancel                # Cancelar ola completa
POST   /harvest/lines/{line_id}/reprogram            # Reprogramar línea
POST   /harvest/lines/{line_id}/confirm              # Confirmar cosecha
```

---

## 🗃️ Modelos de Datos

### **Relaciones Principales**

```
Usuario ←→ UsuarioGranja ←→ Granja ←→ Estanques
                             ↓
                          Ciclos ←→ CicloResumen
                             ↓
                    ┌────────┼────────┐
                    ↓        ↓        ↓
              SiembraPlan  Biometría  CosechaOla
                    ↓                     ↓
            SiembraEstanque       CosechaEstanque
```

### **Estados Clave**

| Entidad | Campo | Valores | Descripción |
|---------|-------|---------|-------------|
| `Usuario` | `status` | `a`/`i` | Activo / Inactivo |
| `Granja` | `is_active` | `1`/`0` | Operativa / Desactivada |
| `Estanque` | `status` | `i`/`a`/`c`/`m` | Inactivo / Activo / Cosecha / Mantenimiento |
| `Estanque` | `is_vigente` | `1`/`0` | Vigente / Baja administrativa |
| `Ciclo` | `status` | `a`/`t` | Activo / Terminado |
| `SiembraPlan` | `status` | `p`/`e`/`f` | Planeado / Ejecución / Finalizado |
| `SiembraEstanque` | `status` | `p`/`f` | Pendiente / Finalizada |
| `CosechaOla` | `tipo` | `p`/`f` | Parcial / Final |
| `CosechaOla` | `status` | `p`/`r`/`x` | Pendiente / Realizada / Cancelada |
| `CosechaEstanque` | `status` | `p`/`c`/`x` | Pendiente / Confirmada / Cancelada |

---

## 🔄 Flujo Operativo

### **1. Setup Inicial**

```mermaid
graph LR
    A[Crear Granja] --> B[Agregar Estanques]
    B --> C[Crear Ciclo Activo]
```

### **2. Proyección con IA** (Opcional pero recomendado)

```mermaid
graph TD
    A[Subir archivo Excel/CSV/PDF] --> B[Gemini interpreta]
    B --> C[Genera proyección_linea]
    C --> D[Autopublica V1]
    D --> E[Generar plan de siembras]
    D --> F[Generar olas de cosecha]
```

### **3. Ciclo de Producción**

```mermaid
graph TD
    A[Crear Plan de Siembras] --> B[Confirmar siembras]
    B --> C[Registrar biometrías]
    C --> D[Crear olas de cosecha]
    D --> E[Confirmar cosechas]
    E --> F{¿Todas finales?}
    F -->|Sí| G[Cerrar ciclo]
    F -->|No| C
```

### **4. Reforecast Automático**

```mermaid
graph LR
    A[Evento operativo] --> B{¿Hay V+1?}
    B -->|No| C[Crear borrador V+1]
    B -->|Sí| D[Actualizar V+1]
    C --> E[Recalibrar PP/SOB]
    D --> E
    E --> F[¿Usuario publica?]
    F -->|Sí| G[V+1 → status=p, is_current=1]
```

---

## 🤖 Sistema de Proyecciones

### **Flujo de Ingesta con IA**

```python
# 1. Usuario sube archivo al crear proyección
POST /proyecciones/cycles/{ciclo_id}/from-file
Content-Type: multipart/form-data
- file: archivo.xlsx
- version: "V1"
- descripcion: "Proyección inicial 2025"

# 2. Backend procesa con Gemini
gemini_service.ingest_file(archivo) → JSON
{
  "semanas": [
    {"semana": 1, "pp_g": 0.5, "sob_pct": 100, "fecha": "2025-01-01"},
    {"semana": 2, "pp_g": 1.2, "sob_pct": 98, "fecha": "2025-01-08"},
    ...
  ]
}

# 3. Crea registros
- proyeccion (status='b', is_current=0)
- proyeccion_linea (N filas, una por semana)

# 4. Autopublica V1
- proyeccion.status = 'p'
- proyeccion.is_current = 1
```

### **Restricciones de Proyecciones**

| Regla | Descripción |
|-------|-------------|
| **1 publicada** | Solo `is_current=1` por ciclo |
| **1 borrador** | Solo `status='b'` por ciclo |
| **V1 autopublica** | La primera versión siempre se publica automáticamente |
| **Parent tracking** | Cada versión guarda `parent_version_id` para trazabilidad |

---

## 📐 Cálculos Pond-First

### **Fórmulas Clave**

#### **Población viva por estanque (i)**

```
N_i(t) = N_sembrados_i - N_retirados_i(t)

Donde:
- N_sembrados_i = densidad_efectiva * superficie_m2
- N_retirados_i(t) = Σ organismos retirados en cosechas hasta t
```

#### **PP real (granja)**

```
PP_real(t) = Σ[PP_i(t) × N_i(t)] / Σ N_i(t)
```

#### **Biomasa viva (granja)**

```
Biomasa_real(kg) = Σ[N_i(t) × PP_i(t)] / 1000
```

#### **SOB real (granja)**

```
SOB_real(%) = [Σ N_i(t) / Σ N_sembrados_i] × 100
```

#### **kg/ha real**

```
kg/ha = Biomasa_real / superficie_activa

Donde superficie_activa = estanques con siembra confirmada y no cosechados final
```

### **Comparativo Real vs Proyección**

```
ΔPP = PP_real - PP_proy
ΔSOB = SOB_real - SOB_proy
ΔBiomasa = Biomasa_real - Biomasa_proy
Δkg/ha = kg/ha_real - kg/ha_proy
%error = (Real - Proy) / max(ε, |Proy|) × 100
```

---

## 🗺️ Roadmap

### **✅ Implementado (v0.1.0)**

- [x] Autenticación JWT
- [x] CRUD Granjas
- [x] CRUD Estanques
- [x] Gestión de Ciclos
- [x] Sistema de Siembras (plan + confirmación)
- [x] Biometrías con SOB operativo
- [x] Cosechas (olas + líneas)
- [x] Logs de auditoría (fechas + SOB)
- [x] Validaciones pond-first (superficie, densidad)
- [x] Zona horaria unificada (Mazatlán)
- [x] Cancelación masiva de olas

### **🚧 En Desarrollo (v0.2.0)**

- [ ] **Proyecciones con Gemini API**
  - [ ] Ingesta de archivos (Excel/CSV/PDF)
  - [ ] Generación automática de `proyeccion_linea`
  - [ ] Autopublicación de V1
  - [ ] Generación de plan de siembras desde proyección
  - [ ] Generación de olas de cosecha desde proyección
- [ ] **Reforecast Vivo**
  - [ ] Detección automática de disparadores
  - [ ] Creación/actualización de V+1 en borrador
  - [ ] Recalibración de PP/SOB proyectado
- [ ] **Cálculos Agregados** (`calculation_service.py`)
  - [ ] Biomasa por estanque → granja
  - [ ] PP ponderado por población
  - [ ] SOB operativo agregado
  - [ ] kg/ha real y proyectado
- [ ] **Servicio de Comparativos** (`comparative_service.py`)
  - [ ] Real vs Proyección por semana
  - [ ] Gráficos de brechas
  - [ ] Alertas de desviaciones

### **🔮 Planeado (v0.3.0+)**

- [ ] **Reportes Avanzados**
  - [ ] Dashboard ejecutivo nivel granja
  - [ ] Análisis de rendimiento por estanque (dashboard de estanque)
  - [ ] Exportación a PDF/Excel
- [ ] **Gestión de Tareas** (`/tasks`)
  - [ ] CRUD de tareas
  - [ ] Tareas recurrentes
- [ ] **Ciclos_resumen** (`/summary_ciclo`)
  - [ ] Para ciclos ya terminados
- [ ] **Sistema de Roles Avanzado**
  - [ ] Permisos granulares por operación
  - [ ] Roles personalizados

---

## 📊 Métricas del Proyecto

```
📦 Módulos implementados: 7/12 (58%)
📝 Líneas de código: ~3,500
🗄️ Tablas BD: 18
🔌 Endpoints: 35+
🧪 Cobertura de tests: 0% (próximamente)