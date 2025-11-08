# 🦐 AquaTrack Backend

Sistema de gestión y proyección inteligente para cultivo de camarón en acuacultura.

**Stack**: Python 3.11+ • FastAPI • SQLAlchemy • MySQL • Google Gemini AI

---

## 📊 Arquitectura del Sistema

### Módulos Implementados ✅

```
AquaTrack/
├── api/                    # Endpoints REST con validación de permisos
│   ├── auth.py            # Autenticación JWT
│   ├── users.py           # ✅ Gestión de usuarios (CON permisos)
│   ├── farms.py           # CRUD granjas
│   ├── ponds.py           # CRUD estanques con versionamiento
│   ├── cycles.py          # Ciclos (CON proyección opcional)
│   ├── seeding.py         # Planes de siembra + sincronización fecha_inicio
│   ├── biometria.py       # Biometrías + SOB operativo + Reforecast
│   ├── harvest.py         # Olas y líneas de cosecha
│   ├── projections.py     # Proyecciones con Gemini AI
│   ├── analytics.py       # ⭐ Dashboards y reportes (CON permisos)
│   └── tasks.py           # ⭐ Sistema de gestión de tareas (CON permisos)
│
├── services/
│   ├── gemini_service.py          # Extractor IA (Excel/CSV/PDF/imágenes)
│   ├── projection_service.py      # Lógica de proyecciones + auto-setup
│   ├── reforecast_service.py      # ⭐ Reforecast automático (3 triggers)
│   ├── calculation_service.py     # ⭐ Cálculos matemáticos centralizados
│   ├── analytics_service.py       # ⭐ Agregación de datos para dashboards
│   ├── task_service.py            # ⭐ Lógica de negocio de tareas
│   ├── cycle_service.py
│   ├── seeding_service.py         # ⭐ Con sincronización de ciclo.fecha_inicio
│   ├── biometria_service.py
│   ├── harvest_service.py         # ⭐ Filtra solo estanques vigentes
│   └── pond_service.py            # ⭐ Con versionamiento y bloqueo selectivo
│
├── models/               # SQLAlchemy ORM
│   ├── user.py          # ⭐ Usuario + UsuarioGranja (con scopes)
│   ├── role.py          # ⭐ Roles del sistema
│   ├── task.py          # ⭐ Tarea + TareaAsignacion
│   └── ...
│
├── schemas/              # Pydantic DTOs
│   ├── task.py          # ⭐ DTOs de tareas
│   └── ...
│
├── utils/                # Helpers
│   ├── permissions.py   # ⭐ Sistema completo de autorización
│   ├── datetime.py      # ⭐ Zona horaria Mazatlán
│   └── db.py
│
└── config/               # Settings (Pydantic)
```

---

## 🔐 Sistema de Permisos (IMPLEMENTADO)

### Arquitectura de Autorización

**Modelo de 2 niveles:**
1. **Membership**: ¿El usuario pertenece a la granja?
2. **Scopes**: ¿El usuario tiene el permiso específico?

### Tipos de Usuarios

#### 👑 Admin Global
- Acceso total a todas las granjas
- Todos los scopes automáticamente
- NO requiere registros en `usuario_granja`

#### 👥 Usuario en Granja
- Registrado en `usuario_granja` con:
  - `rol_id`: Determina scopes por defecto
  - `scopes`: Array JSON con permisos específicos
  - `status`: Estado de la asignación (`a`/`i`)

### Roles Disponibles

| Rol | Descripción | Scopes por Defecto |
|-----|-------------|-------------------|
| **Admin Granja** | Administrador completo de granja | Infraestructura + Operaciones + Tareas + Analytics + Ver usuarios |
| **Biólogo** | Especialista técnico | Operaciones técnicas + Tareas + Analytics + Ver usuarios |
| **Operador** | Personal operativo | Ver/Completar sus tareas + Datos básicos |
| **Consultor** | Solo lectura | `ver_todo` (acceso de lectura completo) |

### Scopes por Módulo

#### Infraestructura
```python
gestionar_estanques   # Crear, editar, eliminar estanques
gestionar_ciclos      # Crear, editar, cerrar ciclos
```

#### Operaciones Técnicas
```python
ver_proyecciones         # Ver proyecciones (requerido para lectura)
gestionar_proyecciones   # CRUD completo de proyecciones
gestionar_siembras       # CRUD planes de siembra
gestionar_cosechas       # CRUD olas y líneas de cosecha
gestionar_biometrias     # CRUD biometrías
```

#### Tareas (⭐ NUEVO)
```python
ver_todas_tareas      # Ver todas las tareas de la granja
ver_mis_tareas        # Ver solo tareas propias (Operador)
gestionar_tareas      # CRUD completo de tareas (bundle)
crear_tareas          # Solo crear tareas
editar_tareas         # Solo editar tareas
eliminar_tareas       # Solo eliminar tareas
asignar_tareas        # Asignar usuarios a tareas
duplicar_tareas       # Duplicar tareas recurrentes
completar_mis_tareas  # Marcar como completada (Operador)
```

#### Analytics
```python
ver_analytics      # Dashboards completos (ciclo, estanque, stats)
ver_datos_basicos  # Info básica operativa (Operador)
```

#### Gestión de Usuarios
```python
ver_usuarios_granja       # Ver lista de usuarios
gestionar_usuarios_granja # Asignar usuarios + cambiar roles
```

### Tabla de Permisos por Rol

| Capacidad | Admin Granja | Biólogo | Operador | Consultor |
|-----------|--------------|---------|----------|-----------|
| **Infraestructura** (estanques, ciclos) | ✅ | ❌ | ❌ | ❌ |
| **Operaciones técnicas** (proyecciones, siembras, cosechas, biometrías) | ✅ | ✅ | ❌ | 👁️ Solo lectura |
| **Tareas** (CRUD completo) | ✅ | ✅ | ❌ | 👁️ Solo lectura |
| **Tareas propias** (ver y completar) | ✅ | ✅ | ✅ | ❌ |
| **Analytics** (dashboards) | ✅ | ✅ | ❌ | ✅ |
| **Datos básicos** | ✅ | ✅ | ✅ | ✅ |
| **Gestión de usuarios** | ✅ (opcional) | ❌ | ❌ | 👁️ Solo lectura |

### Reglas Especiales

#### Lectura Implícita por Membership
Para la mayoría de recursos, **pertenecer a la granja da acceso de LECTURA automático**:
- ✅ Estanques, Ciclos, Siembras, Cosechas, Biometrías (GET sin scope)

#### Lectura Restringida (requiere scope)
- ❌ **Proyecciones**: Requiere `ver_proyecciones`
- ❌ **Tareas**: Requiere `ver_todas_tareas` O `ver_mis_tareas`
- ❌ **Analytics**: Requiere `ver_analytics`
- ❌ **Usuarios**: Requiere `ver_usuarios_granja`

#### Información Contextual
Operadores pueden ver en SUS tareas:
- Nombres de usuarios co-asignados
- Nombre del creador de la tarea
- Info básica del estanque/ciclo relacionado

### Validación en Endpoints

**Patrón estándar:**
```python
# 1. Validar membership (SIEMPRE)
ensure_user_in_farm_or_admin(db, user_id, granja_id, is_admin_global)

# 2. Validar scope (SEGÚN OPERACIÓN)
ensure_user_has_scope(db, user_id, granja_id, Scopes.CREAR_TAREAS, is_admin_global)
```

**Validación compleja (tareas):**
```python
# Ver tareas: diferentes scopes según rol
if user_has_scope(..., Scopes.VER_TODAS_TAREAS, ...):
    return get_all_tasks()  # Admin/Biólogo
elif user_has_scope(..., Scopes.VER_MIS_TAREAS, ...):
    return get_my_tasks()   # Operador
else:
    raise HTTPException(403)
```

---

## 🗄️ Modelo de Datos

### Jerarquía Principal

```
Usuario ↔ UsuarioGranja ↔ Granja ↔ Estanques
       ↓      ↓
      Rol   Scopes (JSON)
                          ↓
                       Ciclos ← CicloResumen (al cerrar)
                          ↓
         ┌────────────────┼────────────────┬─────────────┐
         ↓                ↓                ↓             ↓
    Proyeccion      SiembraPlan      CosechaOla      Tareas
         ↓                ↓                ↓             ↓
  ProyeccionLinea  SiembraEstanque  CosechaEstanque  TareaAsignacion
                        ↓
                   Biometria
                        ↓
                  SOBCambioLog
```

### Estados Clave

| Entidad | Campo | Valores | Descripción |
|---------|-------|---------|-------------|
| `Usuario` | `status` | `a`/`i` | Activo / Inactivo |
| `Usuario` | `is_admin_global` | `1`/`0` | Admin Global / Usuario normal |
| `UsuarioGranja` | `status` | `a`/`i` | Activo / Inactivo en granja |
| `UsuarioGranja` | `scopes` | `JSON` | Array de permisos específicos |
| `Granja` | `is_active` | `1`/`0` | Operativa / Desactivada |
| `Estanque` | `status` | `i`/`a`/`c`/`m`/`d` | Inactivo / Activo / Cosecha / Mantenimiento / Disponible |
| `Estanque` | `is_vigente` | `1`/`0` | Vigente / Versión antigua (versionamiento) |
| `Ciclo` | `status` | `a`/`c` | Activo / Cerrado |
| `Tarea` | `status` | `p`/`e`/`c`/`x` | Pendiente / En progreso / Completada / Cancelada |
| `Tarea` | `prioridad` | `b`/`m`/`a` | Baja / Media / Alta |
| `SiembraPlan` | `status` | `p`/`e`/`f` | Planeado / Ejecución / Finalizado |
| `SiembraEstanque` | `status` | `p`/`f` | Pendiente / Finalizada |
| `Proyeccion` | `status` | `b`/`p`/`r`/`x` | Borrador / Publicada / Revisión / Cancelada |
| `Proyeccion` | `source_type` | `archivo`/`planes`/`reforecast` | Origen de la proyección |
| `CosechaOla` | `tipo` | `p`/`f` | Parcial / Final |
| `CosechaOla` | `status` | `p`/`r`/`x` | Pendiente / Realizada / Cancelada |
| `CosechaEstanque` | `status` | `p`/`c`/`x` | Pendiente / Confirmada / Cancelada |

---

## 🎯 Funcionalidades Core

### 1. Sistema de Gestión de Tareas 📋 (⭐ NUEVO)

#### Características Principales
- **Asignación múltiple**: Varios usuarios responsables por tarea
- **Vinculación flexible**: Opcional con ciclo/estanque
- **Estados**: Pendiente → En progreso → Completada/Cancelada
- **Prioridades**: Baja/Media/Alta
- **Tipos**: Operativa/Administrativa/Mantenimiento (customizable)
- **Tareas recurrentes**: Flag para duplicación fácil
- **Progreso**: Porcentaje de completitud (0-100%)

#### Flujo de Trabajo
```python
# Admin Granja o Biólogo crea tarea
POST /tasks/farms/{granja_id}
  + asignados_ids=[operador1, operador2]
  → Crea tarea con múltiples responsables

# Operador ve solo sus tareas
GET /tasks/farms/{granja_id}
  → Ver tareas propias (filtro automático con ver_mis_tareas)

# Operador actualiza status
PATCH /tasks/{tarea_id}/status
  + status='c', progreso_pct=100
  → Marca como completada (requiere ser responsable)

# Admin/Biólogo ve todas las tareas
GET /tasks/farms/{granja_id}
  → Ve todas las tareas de la granja
```

#### Permisos Específicos
```python
# Crear tarea
Requiere: crear_tareas (incluido en gestionar_tareas)
Admin Granja: ✅  |  Biólogo: ✅  |  Operador: ❌

# Editar tarea
Requiere: editar_tareas (incluido en gestionar_tareas)
Admin Granja: ✅  |  Biólogo: ✅  |  Operador: ❌

# Ver todas las tareas
Requiere: ver_todas_tareas (incluido en gestionar_tareas)
Admin Granja: ✅  |  Biólogo: ✅  |  Operador: ❌

# Ver/Completar tareas propias
Requiere: ver_mis_tareas + completar_mis_tareas
Admin Granja: ✅  |  Biólogo: ✅  |  Operador: ✅

# Duplicar tarea (recurrentes)
Requiere: duplicar_tareas (incluido en gestionar_tareas)
Admin Granja: ✅  |  Biólogo: ✅  |  Operador: ❌

# Eliminar tarea
Requiere: eliminar_tareas + ser creador
Admin Granja: ✅  |  Biólogo: ✅  |  Operador: ❌
```

#### Endpoints
```
POST   /tasks/farms/{granja_id}              # Crear tarea
GET    /tasks/{tarea_id}                     # Detalle (con permisos)
PATCH  /tasks/{tarea_id}                     # Actualizar
PATCH  /tasks/{tarea_id}/status              # Actualizar status (rápido)
DELETE /tasks/{tarea_id}                     # Eliminar
POST   /tasks/{tarea_id}/duplicate           # Duplicar (recurrentes)
GET    /tasks/farms/{granja_id}              # Listar (con filtro de permisos)
GET    /tasks/users/{usuario_id}/tasks       # Tareas de usuario
GET    /tasks/farms/{granja_id}/overdue      # Tareas vencidas
GET    /tasks/farms/{granja_id}/stats        # Estadísticas
```

#### Características Avanzadas
- **Responsables flexibles**: Si no hay asignados, el creador es responsable
- **Lógica automática**: `status='c'` → `progreso_pct=100` automáticamente
- **Duplicación inteligente**: Copia campos relevantes, resetea fechas/progreso
- **Tareas vencidas**: Query optimizado para dashboards
- **Estadísticas**: Agregaciones por estado, prioridad, mes
- **Reasignación**: Cambia asignados eliminando los previos
- **Validación de usuarios**: Verifica existencia antes de asignar

### 2. Gestión de Granjas y Estanques

#### CRUD Básico
- CRUD completo con validación de superficie total
- Estanques con estados operativos y bandera `is_vigente`
- **Validación**: suma de estanques vigentes ≤ superficie total de granja

#### ⭐ Sistema de Versionamiento

**Objetivo**: Preservar datos históricos cuando se modifican atributos críticos (superficie).

**Características**:
```python
# Cambios simples (nombre) → actualización directa
PATCH /ponds/{id} { "nombre": "P1-Nuevo" }
→ ✅ Actualiza mismo estanque

# Cambio de superficie SIN historial → actualización directa
PATCH /ponds/{id} { "superficie_m2": 1500 }
→ ✅ Actualiza mismo estanque (si no tiene siembras/biometrías/cosechas)

# Cambio de superficie CON historial → requiere confirmación
PATCH /ponds/{id} { "superficie_m2": 1500 }
→ ❌ 409 "requiere confirmación"

PATCH /ponds/{id} { "superficie_m2": 1500, "requires_new_version": true }
→ ✅ Crea nueva versión:
   - Estanque original: is_vigente=False (preserva historial)
   - Estanque nuevo: superficie=1500, is_vigente=True
```

**Eliminación Inteligente**:
```python
DELETE /ponds/{id}

# Si tiene historial (siembras/biometrías/cosechas):
→ Soft delete: marca is_vigente=False
→ Retorna 200 con metadata

# Si NO tiene historial:
→ Hard delete: elimina físicamente
→ Retorna 204 No Content
```

#### ⭐ Bloqueo Selectivo

**Objetivo**: Proteger estanques con siembras confirmadas en ciclos activos.

**Reglas**:
```python
# NO permite crear estanques
Si existe ciclo activo (status='a') CON siembras confirmadas (status='f')
→ ❌ 409 "No se pueden crear estanques mientras exista un ciclo activo..."

# NO permite cambiar superficie
Si estanque tiene siembra confirmada en ciclo activo
→ ❌ 409 "No se puede cambiar la superficie de un estanque con siembra..."

# NO permite eliminar
Si estanque tiene siembra confirmada en ciclo activo
→ ❌ 409 "No se puede eliminar un estanque con siembra confirmada..."

# Permite operaciones con:
- Siembras pendientes (status='p')
- Ciclos cerrados (status='c')
- Granjas sin siembras confirmadas
```

### 3. Ciclos de Producción
- **Restricción crítica**: 1 solo ciclo activo por granja
- Estados: `a` (activo) → `c` (cerrado)
- Resumen automático al cerrar ciclo (SOB final, toneladas, kg/ha)
- **Creación con proyección opcional**: archivo procesado con Gemini
- **⭐ NUEVO**: `ciclo.fecha_inicio` se sincroniza automáticamente al confirmar última siembra

### 4. Proyecciones con IA (Gemini) 🤖

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

### 5. Siembras

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

### 6. Biometrías

#### Endpoint de Contexto
```
GET /biometria/cycles/{ciclo_id}/ponds/{estanque_id}/context
```
Retorna SOB operativo actual, datos de siembra, población estimada y valores proyectados. **Llamar antes de mostrar formulario de registro**.

#### Sistema de SOB Operativo
```python
Al sembrar:
  SOB base = 100% automático

Primera biometría:
  Puede usar 100% inicial o actualizarlo

Biometrías posteriores:
  Solo actualiza si hay cambios reales (actualiza_sob_operativa=True)
```

- **⭐ Trigger de Reforecast**: Cada biometría registrada actualiza proyección automáticamente

### 7. Cosechas

#### Confirmación Inteligente
- Obtiene PP de última biometría automáticamente
- **Flexibilidad**:
  ```python
  Si provees biomasa_kg      → deriva densidad_retirada_org_m2
  Si provees densidad_org_m2 → deriva biomasa_kg
  ```
- **⭐ Trigger de Reforecast**: Al confirmar/reprogramar cosecha

### 8. Reforecast Automático 🔮

Sistema que actualiza automáticamente el borrador de proyección cuando ocurren eventos operativos.

#### Triggers Implementados

**✅ TRIGGER 1: Biometrías**
```python
Biometría → Agregación ponderada por población
         → Ancla PP y SOB en semana más cercana
         → Recalcula SOB final objetivo
         → Interpola series con curvas suaves
```

**✅ TRIGGER 2: Siembras**
```python
Al confirmar ÚLTIMA siembra del plan:
  1. Calcula desvío real vs tentativo
  2. Ajusta todas las fechas de proyección
  3. Actualiza ventanas del plan (inicio, fin)
  4. ⭐ Sincroniza ciclo.fecha_inicio con primera siembra real
```

**✅ TRIGGER 3: Cosechas**
```python
Cosecha confirmada → Actualiza retiro en línea de proyección
                  → Recalcula SOB desde cosecha hacia adelante
                  → SOB_después = SOB_antes × (1 - retiro/densidad_base)
```

### 9. Analytics y Dashboards 📊

#### Calculation Service
**Centralización de lógica matemática** - Sin endpoints propios, consumido por otros servicios.

**Funciones implementadas**:
```python
# Cálculos básicos por estanque
calculate_densidad_viva()      # Densidad efectiva (base - retiros) × SOB
calculate_org_vivos()          # Organismos totales = densidad × área
calculate_biomasa_kg()         # Biomasa = org_vivos × (pp_g / 1000)

# Agregaciones ponderadas
calculate_weighted_density()   # Densidad promedio ponderada por superficie
calculate_weighted_pp()        # PP promedio ponderado por población
calculate_global_sob()         # SOB global (reconstruye remanente pre-SOB)
calculate_total_biomass()      # Suma total de biomasa

# Análisis y comparativas
calculate_deviation_pct()      # Desviación % vs proyección
calculate_growth_rate()        # Tasa de crecimiento (g/semana)
```

#### Analytics Service
**Preparación de datos para dashboards** - Consumido por `api/analytics`.

**Funciones principales**:
```python
get_cycle_overview()           # Dashboard general del ciclo
get_pond_detail()              # Detalle individual de estanque
get_growth_curve_data()        # Serie temporal PP (real vs proyectado)
get_biomass_evolution_data()   # Biomasa acumulada
get_density_evolution_data()   # Densidad promedio decreciente
```

**Características**:
- Solo estanques con siembra confirmada
- Fuentes de datos explícitas (`pp_fuente`, `sob_fuente`)
- Sample sizes en KPIs
- Solo proyecciones publicadas
- Filtra automáticamente estanques no vigentes

#### API Endpoints (CON PERMISOS)

```python
GET /analytics/cycles/{ciclo_id}/overview
# Requiere: ver_analytics (incluido en gestionar_tareas)
# Admin Granja: ✅  |  Biólogo: ✅  |  Operador: ❌  |  Consultor: ✅

GET /analytics/ponds/{estanque_id}/detail?ciclo_id={ciclo_id}
# Requiere: ver_analytics (incluido en gestionar_tareas)
# Admin Granja: ✅  |  Biólogo: ✅  |  Operador: ❌  |  Consultor: ✅
```

---

## 📌 API Endpoints

### Autenticación
```
POST   /auth/register              # Registro de usuario
POST   /auth/token                 # Login (retorna JWT)
GET    /auth/me                    # Usuario actual
```

### Usuarios ⭐ (CON PERMISOS)
```
GET    /users                      # Listar usuarios (ver_usuarios_granja)
GET    /users/{id}                 # Detalle de usuario
POST   /users/{id}/farms           # Asignar a granja (gestionar_usuarios_granja)
PATCH  /users/{id}/farms/{gid}     # Cambiar rol (gestionar_usuarios_granja)
DELETE /users/{id}/farms/{gid}     # Desasignar de granja (gestionar_usuarios_granja)
```

### Granjas
```
POST   /farms                      # Crear granja
GET    /farms                      # Listar granjas del usuario
PATCH  /farms/{id}                 # Actualizar granja
```

### Estanques ⭐ (CON VERSIONAMIENTO)
```
POST   /ponds/farms/{granja_id}          # Crear estanque (gestionar_estanques)
GET    /ponds/farms/{granja_id}          # Listar estanques
       ?vigentes_only=true               # Filtrar solo vigentes
GET    /ponds/{id}                       # Detalle de estanque
PATCH  /ponds/{id}                       # Actualizar (gestionar_estanques)
       requires_new_version=true         # Confirmar versionamiento
DELETE /ponds/{id}                       # Soft/Hard delete (gestionar_estanques)
```

### Ciclos
```
POST   /cycles/farms/{granja_id}         # Crear ciclo (gestionar_ciclos)
GET    /cycles/farms/{granja_id}/active  # Ciclo activo
GET    /cycles/farms/{granja_id}         # Listar ciclos
GET    /cycles/{ciclo_id}                # Detalle de ciclo
PATCH  /cycles/{ciclo_id}                # Actualizar (gestionar_ciclos)
POST   /cycles/{ciclo_id}/close          # Cerrar ciclo (gestionar_ciclos)
GET    /cycles/{ciclo_id}/resumen        # Resumen (si cerrado)
```

### Proyecciones (IA)
```
POST   /projections/cycles/{ciclo_id}/from-file  # Subir archivo (gestionar_proyecciones)
GET    /projections/cycles/{ciclo_id}            # Listar (ver_proyecciones)
GET    /projections/cycles/{ciclo_id}/current    # Proyección actual (ver_proyecciones)
GET    /projections/cycles/{ciclo_id}/draft      # Borrador (ver_proyecciones)
GET    /projections/{proyeccion_id}              # Detalle (ver_proyecciones)
PATCH  /projections/{proyeccion_id}              # Actualizar (gestionar_proyecciones)
POST   /projections/{proyeccion_id}/publish      # Publicar (gestionar_proyecciones)
DELETE /projections/{proyeccion_id}              # Cancelar (gestionar_proyecciones)
```

### Siembras
```
POST   /seeding/cycles/{ciclo_id}/plan          # Crear plan (gestionar_siembras)
GET    /seeding/cycles/{ciclo_id}/plan          # Ver plan
POST   /seeding/seedings/{id}/confirm           # Confirmar (gestionar_siembras)
POST   /seeding/seedings/{id}/reprogram         # Reprogramar (gestionar_siembras)
POST   /seeding/seedings/{id}/logs              # Logs de cambios
GET    /seeding/plans/{plan_id}/status          # Status del plan
DELETE /seeding/plans/{plan_id}                 # Eliminar (gestionar_siembras)
```

### Biometrías
```
GET    /biometria/cycles/{ciclo_id}/ponds/{estanque_id}/context  # Contexto
POST   /biometria/cycles/{ciclo_id}/ponds/{estanque_id}          # Registrar (gestionar_biometrias)
GET    /biometria/cycles/{ciclo_id}/ponds/{estanque_id}          # Listar por estanque
GET    /biometria/cycles/{ciclo_id}                              # Listar por ciclo
GET    /biometria/{biometria_id}                                 # Detalle
PATCH  /biometria/{biometria_id}                                 # Actualizar (gestionar_biometrias)
DELETE /biometria/{biometria_id}                                 # Eliminar (gestionar_biometrias)
```

### Cosechas
```
POST   /harvest/cycles/{ciclo_id}/waves         # Crear ola (gestionar_cosechas)
GET    /harvest/cycles/{ciclo_id}/waves         # Listar olas
GET    /harvest/waves/{wave_id}                 # Detalle de ola
POST   /harvest/waves/{wave_id}/cancel          # Cancelar ola (gestionar_cosechas)
POST   /harvest/harvests/{id}/reprogram         # Reprogramar (gestionar_cosechas)
POST   /harvest/harvests/{id}/confirm           # Confirmar (gestionar_cosechas)
```

### Analytics ⭐ (CON PERMISOS)
```
GET    /analytics/cycles/{ciclo_id}/overview    # Dashboard ciclo (ver_analytics)
GET    /analytics/ponds/{estanque_id}/detail    # Dashboard estanque (ver_analytics)
```

### Tareas ⭐ (NUEVO - CON PERMISOS)
```
POST   /tasks/farms/{granja_id}              # Crear tarea (crear_tareas)
GET    /tasks/{tarea_id}                     # Detalle (ver_todas_tareas O responsable)
PATCH  /tasks/{tarea_id}                     # Actualizar (editar_tareas)
PATCH  /tasks/{tarea_id}/status              # Actualizar status (completar_mis_tareas)
DELETE /tasks/{tarea_id}                     # Eliminar (eliminar_tareas + creador)
POST   /tasks/{tarea_id}/duplicate           # Duplicar (duplicar_tareas)
GET    /tasks/farms/{granja_id}              # Listar (ver_todas_tareas O ver_mis_tareas)
GET    /tasks/users/{usuario_id}/tasks       # Tareas de usuario
GET    /tasks/farms/{granja_id}/overdue      # Vencidas (ver_todas_tareas)
GET    /tasks/farms/{granja_id}/stats        # Estadísticas (ver_todas_tareas)
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
- Todas las fechas de servidor (biometrías, logs, tareas)
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
- Solo estanques vigentes cuentan para validaciones

### Permisos y Autorización
```python
# Admin Global
→ Acceso total sin restricciones
→ Bypass de validaciones de membership

# Usuario normal
→ Debe pertenecer a la granja (usuario_granja.status='a')
→ Debe tener el scope específico para la operación
→ Los scopes se resuelven automáticamente:
   - gestionar_* incluye todos los scopes granulares
   - ver_todo (Consultor) da acceso de lectura completo
```

### Sistema de Tareas
```python
# Responsables
Si hay asignaciones → responsables = usuarios asignados
Si NO hay asignaciones → responsable = creador

# Completar tarea
Solo responsables pueden actualizar status
Operador necesita: completar_mis_tareas
Admin/Biólogo necesita: editar_tareas (incluido en gestionar_tareas)

# Visibilidad
ver_todas_tareas → ve todas (Admin, Biólogo)
ver_mis_tareas → ve solo propias (Operador)
```

### Versionamiento de Estanques
```python
# Cambios críticos (superficie con historial)
→ Requiere confirmación (requires_new_version=true)
→ Crea nueva versión (is_vigente=True)
→ Marca versión anterior (is_vigente=False)
→ Preserva historial en versión original

# Cambios simples (nombre, sin historial)
→ Actualización directa
→ No crea nueva versión

# Eliminación
→ Soft delete si tiene historial (is_vigente=False)
→ Hard delete si NO tiene historial (elimina registro)
```

### Bloqueo Selectivo
```python
# Bloquea operaciones críticas en estanques con:
- Siembra confirmada (status='f')
- En ciclo activo (status='a')

# Operaciones bloqueadas:
- Crear nuevos estanques en la granja
- Cambiar superficie del estanque
- Eliminar estanque

# Permite operaciones si:
- Siembras pendientes (status='p')
- Ciclo cerrado (status='c')
- Sin siembras confirmadas
```

### SOB Operativo
```python
SOB base (siembra)      = 100%
SOB después de bio      = valor medido (si actualiza_sob_operativa=True)
SOB después de cosecha  = SOB_antes × (1 - retiro/densidad_base)
```

### Sincronización de Fecha de Inicio
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

## 🚀 Estado Actual - V1 Completada ✅

**✅ Módulos Implementados**:
- [x] Autenticación JWT
- [x] **Sistema completo de permisos por scopes**
- [x] CRUD Granjas + Estanques con versionamiento y bloqueo selectivo
- [x] Gestión de Ciclos
- [x] Sistema de Siembras con sincronización de fecha_inicio
- [x] Biometrías con SOB operativo + endpoint de contexto
- [x] Cosechas (olas + líneas + cancelación masiva)
- [x] Proyecciones con Gemini AI
- [x] Auto-setup condicional con ventana ajustada
- [x] Versionamiento inteligente
- [x] **Reforecast automático (3 triggers completos)**
- [x] Logs de auditoría
- [x] Validaciones pond-first
- [x] Zona horaria unificada
- [x] **Módulo Analytics (dashboards con permisos)**
- [x] **Sistema de Gestión de Tareas (completo con permisos)**

**✅ Sistema de Permisos**:
- [x] 4 roles definidos (Admin Granja, Biólogo, Operador, Consultor)
- [x] ~38 scopes granulares
- [x] Validación de membership + scopes en todos los endpoints
- [x] Resolución automática de scopes "gestionar_*"
- [x] Lectura implícita por membership (ciclos, estanques, etc.)
- [x] Lectura restringida (proyecciones, tareas, analytics)
- [x] Helpers reutilizables (`ensure_user_has_scope`, etc.)
- [x] Admin Global con bypass completo
- [x] Gestión de usuarios en granjas (asignar, cambiar roles)

**✅ Calidad y Testing**:
- [x] Suite de tests de versionamiento de estanques (13/13 pasando)
- [x] Validaciones exhaustivas en todos los endpoints
- [x] Separación clara: Router (validaciones) vs Servicio (lógica)

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
📦 Módulos V1:                14/14 (100%) ✅
🔐 Sistema de permisos:       Implementado completo ✅
📋 Líneas de código:          ~15,000+
🗄️ Tablas BD:                 22
📌 Endpoints:                 75+
🤖 Integración IA:            Google Gemini API v1
🔮 Reforecast:                3/3 triggers implementados ✅
📊 Analytics:                 2 endpoints + servicios completos ✅
📋 Gestión de Tareas:         10 endpoints + servicio completo ✅
🧮 Calculation Service:       15+ funciones matemáticas
🎯 Coverage:                  Siembras confirmadas, fuentes explícitas
⚙️ Versionamiento:            Estanques + Proyecciones ✅
🛡️ Bloqueo Selectivo:         Protección de ciclos activos ✅
🔐 Scopes implementados:      ~38 permisos granulares ✅
👥 Roles del sistema:         4 roles completos ✅
🧪 Testing:                   13/13 tests de versionamiento ✅
```

---

## 📁 Estructura de Archivos Clave

```
AquaTrack/
├── models/
│   ├── user.py                # ⭐ Usuario + UsuarioGranja (con scopes JSON)
│   ├── role.py                # ⭐ Roles del sistema
│   ├── task.py                # ⭐ Tarea + TareaAsignacion (NUEVO)
│   ├── projection.py          # Proyeccion + ProyeccionLinea + SourceType
│   ├── biometria.py           # Biometria + SOBCambioLog + SOBFuente
│   ├── cycle.py               # Ciclo + CicloResumen
│   ├── seeding.py             # SiembraPlan + SiembraEstanque + logs
│   ├── pond.py                # Estanque (con is_vigente)
│   └── ...
│
├── schemas/
│   ├── task.py                # ⭐ TareaCreate/Update/Out (NUEVO)
│   ├── projection.py          # CanonicalProjection + DTOs
│   ├── biometria.py           # BiometriaCreate + BiometriaContextOut
│   ├── cycle.py               # CycleCreate (con validación fechas futuras)
│   ├── pond.py                # PondUpdate (con requires_new_version)
│   └── ...
│
├── services/
│   ├── task_service.py         # ⭐ Lógica de negocio de tareas (NUEVO)
│   ├── gemini_service.py       # Extractor IA con prompt estructurado
│   ├── projection_service.py   # CRUD + auto-setup + sincronización
│   ├── reforecast_service.py   # 3 triggers completos + interpolación
│   ├── seeding_service.py      # Con _sync_cycle_fecha_inicio()
│   ├── biometria_service.py    # Gestión biometrías + SOB + contexto
│   ├── calculation_service.py  # Cálculos puros (mejoras críticas)
│   ├── analytics_service.py    # Agregación (reglas estrictas + vigentes)
│   ├── harvest_service.py      # Con filtro is_vigente
│   ├── pond_service.py         # Versionamiento + bloqueo selectivo
│   └── ...
│
├── api/
│   ├── tasks.py                # ⭐ 10 endpoints de tareas (NUEVO - CON PERMISOS)
│   ├── users.py                # ⭐ Gestión de usuarios (CON PERMISOS)
│   ├── analytics.py            # 2 endpoints dashboards (CON PERMISOS)
│   ├── cycles.py               # Label mejorado "Primera siembra planificada"
│   ├── ponds.py                # Con versionamiento y bloqueo
│   └── ...
│
├── utils/
│   ├── permissions.py          # ⭐ Sistema completo de autorización (NUEVO)
│   ├── datetime_utils.py       # now_mazatlan(), today_mazatlan()
│   ├── db.py                   # get_db()
│   └── ...
│
├── config/
│   └── settings.py             # Variables Gemini + Proyecciones + Reforecast
│
├── tests/
│   └── test_pond_versioning.py # Suite completa (13 tests) ✅
│
└── main.py                     # FastAPI app
```

---

## 🎯 Roadmap Futuro (Post-V1)

### 🟡 Prioridad Media
1. **Notificaciones**: 
   - Alertas push para eventos críticos
   - Recordatorios de operaciones pendientes
   - Resúmenes diarios/semanales
   - Notificaciones de tareas vencidas

2. **Reportes PDF**: 
   - Generación automática de informes de ciclo
   - Exportación de datos históricos
   - Dashboards imprimibles

3. **Analytics Avanzados**: 
   - Comparativas históricas ciclo vs ciclo
   - Proyección de cosecha (fecha óptima, biomasa estimada)
   - Análisis predictivo con IA

### ⚪ Prioridad Baja (V2)
1. **Módulo de Alimentación**: 
   - Registro de alimentación diaria
   - Cálculo de FCR real
   - Optimización de consumo
   - Proyección de costos operativos

2. **Integración con Hardware**:
   - Sensores IoT (temperatura, oxígeno, pH)
   - Alimentadores automáticos
   - Monitoreo en tiempo real

3. **Mobile App**:
   - App nativa para operadores de campo
   - Offline-first para áreas sin conexión
   - Sincronización automática

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
| **Versionamiento** | Sistema de preservación de historial al modificar datos críticos |
| **Soft delete** | Marcado lógico como no vigente (preserva registro) |
| **Hard delete** | Eliminación física del registro de BD |
| **Bloqueo selectivo** | Protección de operaciones en ciclos activos |
| **Estanque vigente** | Versión actual de un estanque (is_vigente=True) |
| **Scope** | Permiso granular para realizar una operación específica |
| **Membership** | Pertenencia de un usuario a una granja |
| **Admin Global** | Usuario con acceso total a todas las granjas |

---

## 🤝 Contribución

Este proyecto sigue una arquitectura limpia con separación de responsabilidades:

- **Models**: Definición de tablas (SQLAlchemy ORM)
- **Schemas**: Validación de entrada/salida (Pydantic)
- **Services**: Lógica de negocio pura (sin validaciones de permisos)
- **API**: Controllers con validaciones de permisos (thin layer)
- **Utils**: Helpers reutilizables (permisos, datetime, db)

**Convenciones**:
- Snake_case para Python
- Comentarios en español
- Docstrings en español
- Type hints obligatorios
- Logs en español
- Validaciones de permisos siempre en el router, nunca en servicios

---

## 📝 Licencia

Proyecto privado - Todos los derechos reservados.

---

**Contexto para IA**: Este sistema gestiona ciclos completos de producción de camarón con un sistema robusto de permisos por scopes. Los usuarios crean granjas con estanques, inician ciclos, cargan proyecciones (manualmente o con IA desde archivos), planifican siembras, registran biometrías, ejecutan cosechas y gestionan tareas operativas. El reforecast automático ajusta las proyecciones en tiempo real conforme se registran datos operativos. El módulo de analytics prepara datos agregados para dashboards visuales con KPIs, gráficas y alertas. El sistema de tareas permite asignación múltiple y gestión completa del flujo de trabajo operativo. Toda la lógica de negocio respeta estados estrictos, permisos granulares y audita cambios críticos. **La sincronización de `ciclo.fecha_inicio` garantiza que la edad del ciclo sea siempre precisa**. **El sistema de versionamiento de estanques preserva historial operativo con protección selectiva en ciclos activos**. **El sistema de permisos implementa autorización de 2 niveles (membership + scopes) con 4 roles predefinidos y ~38 scopes granulares, permitiendo control fino de operaciones por usuario**.
