# Gezpomotor HubSpot Extractor

Primera fase funcional del extractor de datos HubSpot hacia Supabase para **Gezpomotor** (marcas Shacman, Voyah y MHero).

## Objetivo

Extraer información de HubSpot mediante endpoints REST organizados, visualizar respuestas en Swagger y sincronizar datos manualmente hacia Supabase. **Solo lectura** en HubSpot: no se modifica ningún registro.

## Arquitectura

```text
FastAPI (API)
  ├── api/          → Rutas HTTP
  ├── services/     → Lógica de negocio
  ├── clients/      → HubSpot (httpx) y Supabase
  ├── repositories/ → Persistencia en Supabase
  ├── schemas/      → Modelos Pydantic
  └── utils/        → Fechas y serialización
```

Flujo de sincronización:

```text
POST /api/v1/sync/*  →  SyncService (BackgroundTasks)
                     →  HubSpotClient (paginación)
                     →  SupabaseRepository (upsert por lotes)
```

## Requisitos

- Python 3.12+
- Docker y Docker Compose (opcional)
- Proyecto Supabase Cloud con tablas creadas
- Token de HubSpot con permisos de lectura (Private App PAT)

## Variables de entorno

Copia `.env.example` y completa los valores en `.env`:

```env
HUBSPOT_ACCESS_TOKEN=
SUPABASE_URL=
SUPABASE_SECRET_KEY=
APP_ENV=development
APP_VERSION=0.1.0
```

También se aceptan temporalmente los alias `hubspot_api_key` y `hubspot_api_key_service` para el token de HubSpot.

> **Importante:** Nunca subas `.env` al repositorio.

## Crear tablas en Supabase

1. Abre el **SQL Editor** en tu proyecto Supabase.
2. Ejecuta el contenido de `sql/001_initial_schema.sql` (fase 1).
3. Ejecuta el contenido de `sql/002_phase2_associations_quality.sql` (fase 2).
4. Verifica que existan las tablas `hubspot_*`, `sync_*` y `data_quality_*`.

## Ejecución local

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Ejecución con Docker

Levanta **API + frontend** (nginx en el puerto 80, API interna en 8000):

```bash
cp .env.example .env
# Completa HUBSPOT_ACCESS_TOKEN, SUPABASE_URL y SUPABASE_SECRET_KEY

docker compose up --build -d
```

- Dashboard: http://localhost (o `WEB_PORT`, ej. `WEB_PORT=8080 docker compose up -d`)
- Swagger: http://localhost/docs
- Health API: http://localhost/health

PostgreSQL local (opcional, perfil `local-db`; la app usa Supabase en producción):

```bash
docker compose --profile local-db up -d
```

### Actualizar desde GitHub

En el servidor, con el repo clonado y `.env` configurado:

```bash
chmod +x scripts/deploy-from-github.sh
./scripts/deploy-from-github.sh
```

Windows (PowerShell):

```powershell
.\scripts\deploy-from-github.ps1
```

**Despliegue automático:** configura los secrets `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` y `DEPLOY_PATH` en GitHub Actions; el workflow `.github/workflows/deploy-ssh.yml` ejecuta el script en cada push a `main`.

## Swagger

Documentación interactiva: http://localhost:8000/docs

## Endpoints principales

### Salud

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado del servicio |
| GET | `/version` | Versión y entorno |

### Metadatos HubSpot

| Método | Ruta |
|--------|------|
| GET | `/api/v1/hubspot/metadata/contact-properties` |
| GET | `/api/v1/hubspot/metadata/deal-properties` |
| GET | `/api/v1/hubspot/metadata/owners` |
| GET | `/api/v1/hubspot/metadata/deal-pipelines` |
| GET | `/api/v1/hubspot/metadata/association-labels` |

### Contactos y negocios

| Método | Ruta |
|--------|------|
| GET | `/api/v1/hubspot/contacts` |
| GET | `/api/v1/hubspot/contacts/{contact_id}` |
| GET | `/api/v1/hubspot/deals` |
| GET | `/api/v1/hubspot/deals/{deal_id}` |

Los negocios incluyen el campo calculado `brand` según pipeline:

| Pipeline ID | Marca |
|-------------|-------|
| `default` | shacman |
| `1000390393` | voyah |
| `1963395799` | mhero |

### Actividades

| Método | Ruta |
|--------|------|
| GET | `/api/v1/hubspot/activities/calls` |
| GET | `/api/v1/hubspot/activities/meetings` |
| GET | `/api/v1/hubspot/activities/tasks` |
| GET | `/api/v1/hubspot/activities/emails` |
| GET | `/api/v1/hubspot/activities/communications` |
| GET | `/api/v1/hubspot/activities/notes` |

### Sincronización

| Método | Ruta |
|--------|------|
| POST | `/api/v1/sync/metadata` |
| POST | `/api/v1/sync/contacts` |
| POST | `/api/v1/sync/deals` |
| POST | `/api/v1/sync/calls` |
| POST | `/api/v1/sync/meetings` |
| POST | `/api/v1/sync/tasks` |
| POST | `/api/v1/sync/emails` |
| POST | `/api/v1/sync/communications` |
| POST | `/api/v1/sync/notes` |
| POST | `/api/v1/sync/all` |
| GET | `/api/v1/sync/runs` |
| GET | `/api/v1/sync/runs/{sync_id}` |

Body de sincronización:

```json
{
  "sync_type": "full",
  "batch_size": 100
}
```

`sync_type` acepta `full` o `incremental`.

#### Sincronización automática (diaria)

Con `AUTO_SYNC_ENABLED=true`, la API programa un **sync incremental una vez al día** (objetos CRM, actividades y asociaciones):

| Variable | Default | Descripción |
|----------|---------|-------------|
| `AUTO_SYNC_DAILY_AT` | `03:00` | Hora local en `BUSINESS_TIMEZONE` (ej. Colombia) |
| `AUTO_SYNC_INTERVAL_MINUTES` | `1440` | Solo si `AUTO_SYNC_DAILY_AT` está vacío |
| `AUTO_SYNC_BATCH_SIZE` | `100` | Tamaño de lote |

Para desactivar la hora fija y usar solo intervalo: `AUTO_SYNC_DAILY_AT=` (vacío) y ajusta `AUTO_SYNC_INTERVAL_MINUTES`.

Reinicia la API o el contenedor `api` tras cambiar estas variables.

```bash
ruff check .
pytest
```

Las pruebas usan mocks y no consumen HubSpot ni Supabase reales.

## Seguridad

- Secretos en `.env` con `SecretStr` en configuración.
- CORS limitado a localhost en desarrollo.
- `SUPABASE_SECRET_KEY` solo en backend.
- `.env` excluido de Docker y Git.

## Limitaciones de esta fase

- Sincronizaciones en `BackgroundTasks` (se migrará a worker dedicado).
- No hay dashboard ni aplicación de escritorio.
- Sin autenticación en la API (uso interno/desarrollo).

---

## Fase 2: Asociaciones y calidad de datos

### Objetivo

1. **Sincronizar asociaciones** entre contactos, negocios y actividades desde HubSpot hacia `hubspot_associations`.
2. **Evaluar calidad de datos** con un motor de reglas independiente de las rutas HTTP.

La fase 1 (metadata, contactos, negocios) **no se modifica** en comportamiento.

### Migración 002

Ejecuta en el SQL Editor de Supabase:

```text
sql/002_phase2_associations_quality.sql
```

Esta migración:

- Amplía `hubspot_associations` con `raw_payload`, `is_active`, `last_seen_at`.
- Crea `data_quality_rules`, `data_quality_runs`, `data_quality_results`.
- Inserta 24 reglas iniciales de calidad.

No borra datos existentes.

### Variables de entorno adicionales

```env
DATA_QUALITY_STALE_DEAL_DAYS=30
ALLOW_FULL_PHASE2_VALIDATION=false
PHASE2_VALIDATION_SAMPLE_SIZE=50
```

| Variable | Descripción |
|----------|-------------|
| `DATA_QUALITY_STALE_DEAL_DAYS` | Umbral en días para la regla `DEAL_STALE` |
| `ALLOW_FULL_PHASE2_VALIDATION` | Si es `true`, el script de validación sincroniza todas las asociaciones |
| `PHASE2_VALIDATION_SAMPLE_SIZE` | Tamaño de muestra cuando la validación completa está desactivada |

### Asociaciones soportadas

Dirección normalizada (no se guardan duplicados inversos):

| Origen | Destino |
|--------|---------|
| contact | deal |
| contact | call, meeting, task, email, communication, note |
| deal | call, meeting, task, email, communication, note |

Extracción vía HubSpot CRM v4 batch read con lotes configurables y reintentos ante `429`.

### Endpoints de asociaciones (lectura, paginados)

| Método | Ruta |
|--------|------|
| GET | `/api/v1/hubspot/associations/types` |
| GET | `/api/v1/hubspot/associations/contact-deal` |
| GET | `/api/v1/hubspot/associations/contact-activities` |
| GET | `/api/v1/hubspot/associations/deal-activities` |

### Sincronización de asociaciones

| Método | Ruta |
|--------|------|
| POST | `/api/v1/sync/associations/contact-deal` |
| POST | `/api/v1/sync/associations/contact-activities` |
| POST | `/api/v1/sync/associations/deal-activities` |
| POST | `/api/v1/sync/associations/all` |

Body:

```json
{
  "sync_type": "full",
  "batch_size": 100
}
```

`sync_type`: `full` o `incremental` (solapamiento de 15 minutos sobre objetos modificados).

Respuesta inmediata:

```json
{
  "sync_id": "uuid",
  "status": "started",
  "message": "Sincronización de asociaciones iniciada"
}
```

No se permiten dos sincronizaciones del mismo grupo simultáneas.

#### Ejemplo: asociación full

```bash
curl -X POST http://localhost:8000/api/v1/sync/associations/contact-deal \
  -H "Content-Type: application/json" \
  -d '{"sync_type": "full", "batch_size": 100}'
```

Consulta el progreso en `GET /api/v1/sync/runs/{sync_id}`.

#### Ejemplo: asociación incremental

```bash
curl -X POST http://localhost:8000/api/v1/sync/associations/contact-deal \
  -H "Content-Type: application/json" \
  -d '{"sync_type": "incremental", "batch_size": 100}'
```

El cursor solo avanza si la sincronización termina correctamente.

### Calidad de datos

| Método | Ruta |
|--------|------|
| POST | `/api/v1/data-quality/run` |
| GET | `/api/v1/data-quality/runs` |
| GET | `/api/v1/data-quality/runs/{run_id}` |
| GET | `/api/v1/data-quality/results` |
| GET | `/api/v1/data-quality/summary` |

Ejecutar análisis:

```bash
curl -X POST http://localhost:8000/api/v1/data-quality/run \
  -H "Content-Type: application/json" \
  -d '{"scope": "all"}'
```

Scopes: `all`, `contacts`, `deals`, `activities`, `associations`.

Filtros en `/results`: `rule_code`, `object_type`, `severity`, `is_resolved`, `hubspot_id`, `limit`, `offset`.

#### Reglas implementadas

**Contactos:** `CONTACT_WITHOUT_OWNER`, `CONTACT_WITHOUT_EMAIL_AND_PHONE`, `CONTACT_WITHOUT_LIFECYCLE_STAGE`, `CONTACT_WITHOUT_SOURCE`, `CONTACT_WITHOUT_BRAND`, `CONTACT_WITH_INVALID_EMAIL`, `CONTACT_WITHOUT_NAME`

**Negocios:** `DEAL_WITHOUT_OWNER`, `DEAL_WITHOUT_CONTACT`, `DEAL_WITHOUT_PIPELINE`, `DEAL_WITHOUT_STAGE`, `DEAL_WITHOUT_AMOUNT`, `DEAL_WITH_UNKNOWN_PIPELINE`, `DEAL_WITH_INVALID_STAGE`, `DEAL_WITHOUT_ACTIVITY`, `DEAL_STALE`, `DEAL_CLOSED_WITHOUT_CLOSE_DATE`, `DEAL_WON_WITHOUT_AMOUNT`

**Actividades y asociaciones:** `ACTIVITY_WITHOUT_CONTACT_OR_DEAL`, `ACTIVITY_WITHOUT_OWNER`, `ACTIVITY_WITHOUT_TIMESTAMP`, `CONTACT_WITHOUT_DEAL`, `DEAL_WITHOUT_ACTIVITY_ASSOCIATION`, `ASSOCIATION_REFERENCES_MISSING_OBJECT`

#### Severidades

| Nivel | Uso |
|-------|-----|
| `info` | Observaciones menores |
| `warning` | Datos incompletos o inconsistentes |
| `critical` | Problemas que afectan operación o reporting |

Los hallazgos activos no se duplican entre ejecuciones. Si un problema se corrige en HubSpot/Supabase, el hallazgo anterior se marca `is_resolved = true` sin borrar histórico.

### Validar idempotencia

1. Ejecuta sync full de asociaciones.
2. Anota el conteo en `hubspot_associations` (solo `is_active = true`).
3. Repite la misma sync: el conteo no debe aumentar.
4. Usa el script operativo:

```powershell
.venv\Scripts\python scripts\validate_phase2.py
```

Con `ALLOW_FULL_PHASE2_VALIDATION=true` en `.env` se ejecuta sincronización completa; de lo contrario usa muestra limitada.

### Limitaciones conocidas (fase 2)

- Procesamiento en segundo plano con `BackgroundTasks` (sin Redis/Celery).
- Eliminación de asociaciones obsoletas usa `is_active`/`last_seen_at` en lugar de borrado físico cuando no hay certeza total.
- Inferencia de marca en contactos documentada en `app/services/data_quality/brand_inference.py`; si no es confiable, `brand = null`.
- Pipelines sin mapeo (ej. `1001269971`) generan `DEAL_WITH_UNKNOWN_PIPELINE`.

## Próximas fases

- Dashboard web por marca (Shacman, Voyah, MHero).
- Worker de sincronización programada.
- Políticas RLS para cliente público.
- Instalador `.exe`.

## Archivo requests.http

Incluye ejemplos listos para VS Code REST Client o extensiones compatibles.
