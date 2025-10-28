# AquaTrack Backend — Documentación del código (v0.1.0)

> **Stack:** FastAPI · SQLAlchemy 2.0 ORM · MySQL (PyMySQL) · Pydantic v2 · JWT (python-jose) · passlib/bcrypt · CORS

> **Estado:** Auth & RBAC funcionales; Farms/Ponds/Cycles/Seeding implementados. `health` público. `db` (opcional) aún no expuesto. Frontend a posteriori.

---

## 1) Guía rápida (Runbook)

### Variables de entorno (`.env`)

* `DATABASE_URL`: `mysql+pymysql://<user>:<pass>@<host>:3306/<db>`
* `SECRET_KEY`: clave JWT **secreta** (alta entropía).
* `ACCESS_TOKEN_EXPIRE_MINUTES`: minutos de vigencia del access token (por defecto 720 = 12 h).
* `CORS_ALLOW_ORIGINS`: lista JSON con orígenes permitidos (ej. `["http://localhost:4200"]`).

### Arranque

```bash
uvicorn main:app --reload --port 8000
```

* Docs Swagger: `GET /docs`
* Redoc: `GET /redoc`
* Healthcheck: `GET /health` → `{ "status": "ok" }`

### Autenticación

* **Password grant**: `POST /auth/token` (form-urlencoded: `username`, `password`).
* **Registro**: `POST /auth/register`
* **Perfil**: `GET /auth/me` (Bearer).

**Bearer token** en `Authorization: Bearer <jwt>` para todo lo demás.

---

## 2) Seguridad & Permisos

### 2.1. Autenticación

* `OAuth2PasswordBearer(tokenUrl="/auth/token")` (utils.security).
* Tokens JWT firmados HS256: `sub=<usuario_id>`, `exp=<UTC+ttl>`.

### 2.2. Obtención de usuario actual

* `utils.dependencies.get_current_user` decodifica JWT y trae `Usuario` activo (`status='a'`).

### 2.3. Autorización por recurso (RBAC por granja)

* **Admin global** (`Usuario.is_admin_global=True`): acceso a todas las granjas.
* **Miembro de granja** (tabla `usuario_granja` con `status='a'`): acceso a endpoints de esa granja.
* Helper central: `utils.permissions.ensure_user_in_farm_or_admin(db, user_id, granja_id, is_admin_global)`.

### 2.4. Matriz rápida de permisos (endpoints presentes)

| Recurso | Endpoint                                                   | Permiso                                                                  |
| ------- | ---------------------------------------------------------- | ------------------------------------------------------------------------ |
| Auth    | `POST /auth/token`, `POST /auth/register`, `GET /auth/me`  | Público (token) / Público (registro) / Autenticado                       |
| Health  | `GET /health`                                              | Público                                                                  |
| Farms   | `GET /farms`                                               | Autenticado (hoy: lista todas; filtrado por usuario en iteración futura) |
| Farms   | `POST /farms`                                              | **Solo admin global**                                                    |
| Farms   | `PUT /farms/{granja_id}`                                   | **Solo admin global**                                                    |
| Ponds   | `POST /ponds/farms/{granja_id}`                            | Miembro de granja o admin global                                         |
| Ponds   | `GET /ponds/farms/{granja_id}`                             | Miembro de granja o admin global                                         |
| Ponds   | `GET /ponds/{estanque_id}`                                 | Miembro de granja (del estanque) o admin global                          |
| Ponds   | `PATCH /ponds/{estanque_id}`                               | Miembro de granja (del estanque) o admin global                          |
| Cycles  | `POST /cycles/farms/{granja_id}`                           | Miembro de granja o admin global                                         |
| Cycles  | `GET /cycles/farms/{granja_id}/active`                     | Miembro de granja o admin global                                         |
| Cycles  | `GET /cycles/farms/{granja_id}`                            | Miembro de granja o admin global                                         |
| Cycles  | `GET /cycles/{ciclo_id}`                                   | Miembro de granja (del ciclo) o admin global                             |
| Cycles  | `PATCH /cycles/{ciclo_id}`                                 | Miembro de granja (del ciclo) o admin global                             |
| Cycles  | `POST /cycles/{ciclo_id}/close`                            | Miembro de granja (del ciclo) o admin global                             |
| Cycles  | `GET /cycles/{ciclo_id}/resumen`                           | Miembro de granja (del ciclo) o admin global                             |
| Seeding | `POST /seeding/cycles/{ciclo_id}/plan`                     | Miembro de granja (del ciclo) o admin global                             |
| Seeding | `GET /seeding/cycles/{ciclo_id}/plan`                      | Miembro de granja (del ciclo) o admin global                             |
| Seeding | `POST /seeding/plan/{siembra_plan_id}/ponds/{estanque_id}` | Miembro de granja o admin global                                         |
| Seeding | `POST /seeding/seedings/{siembra_estanque_id}/reprogram`   | Miembro de granja o admin global                                         |
| Seeding | `POST /seeding/seedings/{siembra_estanque_id}/confirm`     | Miembro de granja o admin global                                         |
| Seeding | `DELETE /seeding/plan/{siembra_plan_id}`                   | Miembro de granja o admin global                                         |

> **Checklist:** Todos los routers usan `get_current_user` y llaman a `ensure_user_in_farm_or_admin` cuando se requiere asociar el recurso a una granja/ciclo/estanque específico.
> `Farms` protege creación/edición con **admin global**. `Health` queda público.

---

## 3) Diseño de capas

```
main.py → api/router.py → api/* (routers)
            ↓
         services/* (reglas de negocio/validaciones)
            ↓
         models/* (ORM) ↔ schemas/* (Pydantic I/O)
            ↓
         utils/* (auth, db, permisos, seguridad)
```

* **Routers**: orquestan dependencias (DB, usuario), validan permisos y delegan en services.
* **Services**: encapsulan reglas de negocio, validaciones y transacciones.
* **Models**: entidades ORM (SQLAlchemy 2.0).
* **Schemas**: contratos de entrada/salida (Pydantic v2).
* **Utils**: DB engine/session, JWT, hashing, helpers de permisos, dependencias FastAPI.

---

## 4) Modelado de datos (SQLAlchemy)

### 4.1. Usuarios y roles

* `Usuario`: autenticación, `is_admin_global`, estado `a/i`.
* `Rol`: catálogo de roles (negocio).
* `UsuarioGranja`: asociación usuario–granja–rol (`status a/i`, `UNIQUE(usuario, granja)`).

### 4.2. Granjas y estanques

* `Granja`: superficie total (`superficie_total_m2`), `is_active`. Relaciones: `estanques`, `ciclos`.
* `Estanque`: `status` (`i/a/c/m`), `is_vigente` (incluye en capacidad vigente), superficie propia.

**Reglas clave de superficie**

* Al **crear/editar** estanque **vigente**, la suma de superficies vigentes **no debe exceder** `superficie_total_m2` de su granja.
* Al **actualizar** granja, no se puede reducir `superficie_total_m2` por debajo de la suma vigente actual.

### 4.3. Ciclos

* `Ciclo`: por granja, `status` `a` (activo) o `t` (terminado). Una granja **no puede** tener 2 activos.
* `CicloResumen`: snapshot al cierre (SOB final, toneladas, estanques cosechados, fechas real inicio/fin, notas).

### 4.4. Siembras

* `SiembraPlan`: **único por ciclo** (`UNIQUE(ciclo_id)`), ventana `[inicio, fin]`, densidad y talla org.
* `SiembraEstanque`: una por estanque dentro del plan; `status` `p/f`; overrides opcionales.
* `SiembraFechaLog`: historial de reprogramaciones (fecha anterior/nueva, motivo, responsible, timestamp).

---

## 5) Esquemas (Pydantic) — contratos I/O útiles

* `schemas.user`: `UserCreate`, `UserOut`, `Token`.
* `schemas.farm`: `FarmCreate` (con estanques anidados opcionales), `FarmUpdate`, `FarmOut`.
* `schemas.pond`: `PondCreate`, `PondUpdate`, `PondOut`.
* `schemas.cycle`: `CycleCreate`, `CycleUpdate`, `CycleClose`, `CycleOut`, `CycleResumenOut`.
* `schemas.seeding`: `SeedingPlanCreate/Out`, `SeedingCreateForPond`, `SeedingReprogramIn`, `SeedingOut`, `SeedingPlanWithItemsOut`.

> Notas de validación:
>
> * `condecimal` se usa para superficies/densidades/tallas (precisión controlada).
> * En reprogramación, `0` en `densidad_override_org_m2` o `talla_inicial_override_g` **no cambia** (se ignora).
> * `null` en cualquier campo de reprogramación = **no cambiar**.

---

## 6) Servicios (reglas de negocio clave)

### 6.1. `services/auth_service.py`

* `authenticate_user` — valida credenciales, estado, actualiza `last_login_at`.
* `issue_access_token` — emite JWT con `sub=usuario_id`.
* `create_user` — alta, con unicidad `username/email`.

### 6.2. `services/farm_service.py`

* `list_farms` — devuelve todas (ordenadas por nombre).
* `create_farm` — valida suma de superficies de estanques **vigentes** anidados vs `superficie_total_m2`. Inicializa estanques como `status='i'`.
* `update_farm` — si cambia `superficie_total_m2`, valida que no quede por debajo de la suma vigente actual.

### 6.3. `services/pond_service.py`

* `create_pond` — valida capacidad al marcarse vigente. Siempre crea `status='i'`.
* `update_pond` — valida nueva suma de superficies vigentes **excluyendo** el estanque que se actualiza.

### 6.4. `services/cycle_service.py`

* `create_cycle` — requiere granja activa; impide dos ciclos activos por granja.
* `update_cycle` — no permite editar si `status='t'`.
* `close_cycle` — marca `t`, fija `fecha_cierre_real` y crea `CicloResumen`. **TODO futuro:** calcular `sob_final`, `toneladas`, `n_estanques` desde `calculation_service` (hoy mockeado).

### 6.5. `services/seeding_service.py`

* `create_plan_and_autoseed` — crea plan (único por ciclo) y genera **auto** `SiembraEstanque` para todos los estanques **vigentes** de la granja, distribuyendo `fecha_tentativa` uniformemente en la ventana.
* `get_plan_with_items_by_cycle` — trae plan (404 si no existe).
* `create_manual_seeding_for_pond` — agrega siembra manual para un estanque vigente que no tenga ya una en el plan.
* `reprogram_seeding` —

  * Si `fecha_nueva` cambia → agrega `SiembraFechaLog` (con `motivo` opcional).
  * Overrides: `None` o `0` = **no cambio**; diferente de `0` = **actualiza**.
  * `lote`: `None` no cambia, `""` limpia.
* `confirm_seeding` — idempotente: marca `f`, fija `fecha_siembra=HOY`, **activa** estanque (`status='a'`), y si el plan estaba `p` lo pasa a `e`.
* `delete_plan_if_no_confirmed` — elimina plan + siembras si no existe ninguna confirmada; si hay confirmadas → `409`.

---

## 7) Rutas — referencia rápida con ejemplos

> **Convención general**: Todas las rutas (excepto `health`, `auth/token`, `auth/register`) requieren **Bearer token**.

### 7.1. Auth (`api/auth.py`)

* `POST /auth/token` — **login** (form-url-encoded)

```bash
curl -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=jdoe&password=secret" \
  http://localhost:8000/auth/token
```

* `POST /auth/register` — alta usuario
* `GET /auth/me` — usuario actual

### 7.2. Farms (`api/farms.py`)

* `GET /farms` — **lista** (hoy sin filtro por usuario; iteración futura lo limitará)
* `POST /farms` — **crear** (solo admin global)
* `PUT /farms/{granja_id}` — **actualizar** (solo admin global)

### 7.3. Ponds (`api/ponds.py`)

* `POST /ponds/farms/{granja_id}` — crear estanque en granja (siempre `status='i'`)
* `GET /ponds/farms/{granja_id}` — listar estanques de la granja
* `GET /ponds/{estanque_id}` — detalle
* `PATCH /ponds/{estanque_id}` — actualizar (`superficie_m2`, `is_vigente`, `nombre`)

### 7.4. Cycles (`api/cycles.py`)

* `POST /cycles/farms/{granja_id}` — crear ciclo (garantiza 1 activo por granja)
* `GET /cycles/farms/{granja_id}/active` — ciclo activo
* `GET /cycles/farms/{granja_id}` — lista (filtro `include_terminated=false` por defecto)
* `GET /cycles/{ciclo_id}` — detalle
* `PATCH /cycles/{ciclo_id}` — actualizar (no permitido si `t`)
* `POST /cycles/{ciclo_id}/close` — cerrar + snapshot `CicloResumen` (valores agregados aún mock)
* `GET /cycles/{ciclo_id}/resumen` — obtener snapshot (404 si no existe)

### 7.5. Seeding (`api/seeding.py`)

* `POST /seeding/cycles/{ciclo_id}/plan` — crea plan **único** por ciclo y autogenera siembras distribuidas.
* `GET /seeding/cycles/{ciclo_id}/plan` — devuelve plan + siembras.
* `POST /seeding/plan/{siembra_plan_id}/ponds/{estanque_id}` — crea siembra manual para estanque faltante.
* `POST /seeding/seedings/{siembra_estanque_id}/reprogram` — reprogramación *idempotente* de campos (semántica `null/0` ya descrita).
* `POST /seeding/seedings/{siembra_estanque_id}/confirm` — confirma siembra: `status='f'`, setea `fecha_siembra` y activa estanque.
* `DELETE /seeding/plan/{siembra_plan_id}` — elimina plan si no hay confirmadas.

---

## 8) Contratos y códigos de error frecuentes

* `401 Unauthorized` — token inválido/expirado; usuario inexistente o inactivo.
* `403 Forbidden` — no pertenece a la granja y no es admin global.
* `404 Not Found` — recurso inexistente (`Granja`, `Ciclo`, `Plan`, `Estanque`, `Siembra`).
* `409 Conflict` —

  * Crear ciclo cuando ya hay uno activo.
  * `superficie_total_m2` insuficiente vs suma de estanques vigentes.
  * Intento de crear/duplicar siembra en plan, o eliminar plan con siembras confirmadas.
  * Reprogramar siembra ya confirmada.
* `400 Bad Request` —

  * `ventana_inicio > ventana_fin`.
  * Editar ciclo terminado (`status='t'`).

---

## 9) Seguridad & buenas prácticas

* **No commitear `.env`** (ya en `.gitignore`). Mantener `SECRET_KEY` fuera de repositorio.
* **Hash de contraseñas** con `passlib[bcrypt]`.
* JWT firmado HS256. **Rotar** `SECRET_KEY` solo con estrategia de sesión (invalidará tokens).
* **CORS**: restringir orígenes en prod.
* **DB pool**: `pool_pre_ping=True`, `pool_recycle=3600`.

---

## 10) Roadmap técnico corto (anotaciones TODO)

* `calculation_service` → cálculo real de `sob_final`, `toneladas_cosechadas`, `n_estanques` al cerrar ciclo.
* **Filtro por usuario** en `GET /farms` (usar `UsuarioGranja`).
* **Scopes/roles** más finos por acción (crear/editar ponds y ciclos según rol dentro de la granja).
* **Endpoint DB** opcional (p. ej., `GET /db/ping`) si se desea health extendido.
* **Métricas/Logging** (tiempos, 4xx/5xx).
* **Soft-delete** opcional (flags/estados) si negocio lo requiere.

---

## 11) Snippets de docstring sugeridos (copy‑paste)

> Puedes pegar estos bloques arriba de cada función/método para enriquecer la autodoc.

### `utils.permissions.ensure_user_in_farm_or_admin`

```python
"""Verifica autorización por contexto de granja.

- **Admin global** salta la verificación.
- Si no es admin, exige que exista un registro activo en `usuario_granja` para `user_id` y `granja_id`.

Levanta 403 si no cumple.
"""
```

### `services/seeding_service.create_plan_and_autoseed`

```python
"""Crea el plan de siembras **único por ciclo** y autogenera siembras
para todos los estanques **vigentes** de la granja.

- Distribuye `fecha_tentativa` uniformemente a lo largo de `[ventana_inicio, ventana_fin]`.
- Valida que la ventana sea correcta (`inicio <= fin`).
- `status` inicial del plan: `p` (planeado).
"""
```

### `services/seeding_service.reprogram_seeding`

```python
"""Reprograma una siembra pendiente.

Semántica de `payload`:
- `fecha_nueva`: si es distinta, actualiza y guarda un `SiembraFechaLog`.
- `densidad_override_org_m2` y `talla_inicial_override_g`: `None` o `0` → **no cambian**; otro valor → **actualiza**.
- `lote`: `None` no cambia; string (incl. "") asigna/limpia.

No permite reprogramar si `status='f'` (confirmada).
"""
```

### `services/cycle_service.close_cycle`

```python
"""Cierra un ciclo: marca `status='t'`, fija `fecha_cierre_real` y
crea `CicloResumen` con métricas agregadas.

**Nota:** Las métricas (`sob_final`, `toneladas`, `n_estanques`) hoy se
inyectan como parámetros (mock). Futuro: calcular en `calculation_service`.
"""
```

### `services/pond_service.update_pond`

```python
"""Actualiza metadatos del estanque y valida capacidad de la granja.

Calcula la suma de superficies de estanques **vigentes** (excluyendo el propio)
y verifica que `nueva_suma <= superficie_total_m2` de la granja.

No modifica `status` operativo del estanque.
"""
```

---

## 12) Ejemplos de flujo (E2E)

### 12.1. Crear granja + estanques + ciclo + plan de siembras

1. **Login** → JWT.
2. **Crear granja** (admin global) con estanques anidados (`status` se ignora y quedan `i`).
3. **Crear ciclo** para esa granja.
4. **Crear plan de siembras** → se autogeneran siembras (`p`) para todos los estanques **vigentes**.
5. **Confirmar siembras** a medida que suceden → activan sus estanques (`status='a'`).
6. **Cerrar ciclo** → genera `CicloResumen`.

### 12.2. Reprogramar siembra

* Llamar a `POST /seeding/seedings/{id}/reprogram` con los campos a modificar. `null/0` no modifican.
* Si cambia la fecha, se registra en `SiembraFechaLog`.

---

## 13) Observaciones de calidad

* **Encoding**: hay caracteres acentuados mal codificados en algunos `detail` ("inválidas" → `invÃ¡lidas`). Recomendado: guardar fuente en UTF‑8 y revisar fuentes/IDE.
* **Tipos decimales**: usas `Numeric` en DB y `Decimal` en servicios para sumatorias → 👍 (evita artefactos float). Mantener consistente.
* **Idempotencia**: `confirm_seeding` devuelve el recurso si ya estaba `f` → 👍.
* **Transacciones**: en `create_farm` se usa `flush()` para obtener `granja_id` antes de insertar estanques → correcto.

---

## 14) Anexo: Checklist de revisión

* [x] **Auth** funciona (login/register/me) y encripta con bcrypt.
* [x] **JWT** con `sub` y `exp` (HS256); `decode` seguro.
* [x] **CORS** lee orígenes desde `.env`.
* [x] **RBAC** por granja aplicado en Ponds/Cycles/Seeding; Farms restringe POST/PUT a admin global.
* [x] **Único plan por ciclo** (constraint + lógica).
* [x] **Health** público.
* [ ] **Endpoint DB opcional** (ping/diagnóstico) — *pendiente si se desea*.
* [ ] **Cálculo de métricas reales** al cerrar ciclo — *pendiente.*

---

**Fin.**
