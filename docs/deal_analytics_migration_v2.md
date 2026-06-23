# Migración — Metodología de evaluación v2

## Cambios realizados

### Nuevos módulos Python

| Módulo | Función |
|--------|---------|
| `evaluation_config.py` | Pesos, SLA por etapa, umbrales |
| `contact_classification.py` | Taxonomía canónica de contacto |
| `contact_eligibility.py` | Negocios elegibles |
| `activity_attribution.py` | Resolución y deduplicación actividad→deal |
| `operational_scores.py` | Disciplina operativa, efectividad comercial |
| `first_response.py` | Primera respuesta desde asignación |
| `next_action.py` | Estado de próxima acción |
| `risk_dimensions.py` | Dimensiones de riesgo independientes |
| `activity_origin.py` | Origen humano/automático |
| `evaluation_metadata.py` | Frescura y trazabilidad |

### Campos API nuevos (con aliases legacy)

| Nuevo | Alias deprecated |
|-------|------------------|
| `discipline_operational_score` | `discipline_contact_score` (cuando hay dato v2) |
| `legacy_discipline_contact_score` | fórmula antigua explícita |
| `management_discipline_score` | `discipline_score` |
| `commercial_effectiveness_score` | — |
| `legacy_effectiveness_commercial_score` | `effectiveness_commercial_score` |
| `channel_overdue_21d` | `overdue_contact_21d` |
| `historical_overdue_task_count` | — |
| `operational_overdue_task_count` | `overdue_task_count` (operativo) |

### SQL

Ejecutar: `sql/010_evaluation_methodology_v2.sql`

- Columnas históricas/operativas en `deal_analytics`
- Tabla `deal_owner_history`

### Frontend

- Label «Sin llamada ni WhatsApp en 21 días»
- «Disciplina operativa» en metodología de contacto
- Tooltips actualizados en `metricTooltips.ts`

---

## Despliegue

```powershell
# 1. Migración DB
# Ejecutar 010_evaluation_methodology_v2.sql en Supabase

# 2. Tests
.\.venv\Scripts\python.exe -m pytest tests/test_evaluation_methodology_v2.py tests/test_contact_metrics.py tests/test_task_semantics.py -q

# 3. Refresh analítica (pobla historical_* en deal_analytics)
.\.venv\Scripts\python.exe scripts/run_deal_analytics_refresh.py

# 4. Reiniciar API
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 5. Frontend
cd frontend; npm run build
```

---

## Rollback

1. Revertir commit de código (aliases legacy mantienen compatibilidad parcial).
2. Columnas SQL nuevas son aditivas; no es obligatorio eliminarlas.
3. `deal_owner_history` puede quedar vacía sin romper lecturas.

---

## Validación post-despliegue

- [ ] `legacy_discipline_contact_score` ≠ `discipline_operational_score` en marcas con baja cobertura
- [ ] Negocio cerrado: `historical_overdue_task_count` > 0 si aplica; `operational_overdue_task_count` = 0
- [ ] Llamada 1s sin outcome: no `connected` en clasificación v2
- [ ] API envelope incluye `evaluation_metadata`
- [ ] Gráfica semanal y cobertura usan mismos conteos atribuidos (revisar `attribution_quality`)

---

## No implementado en esta entrega (y motivo)

| Ítem | Motivo |
|------|--------|
| Sync `propertiesWithHistory` para `hubspot_owner_id` | Requiere extensión sync HubSpot; fallback documentado |
| Festivos en minutos hábiles | Sin calendario en proyecto |
| SLA por stage_id HubSpot real | Mapeo inicial por `commercial_group`; extensible en `evaluation_config.py` |
| Origen WA humano/bot fiable | Propiedades HubSpot insuficientes en sync actual |
| Cohortes maduras con lag configurable | Estructura en `commercial_effectiveness_score`; UI de cohorte pendiente |
| Migración datos a `deal_owner_history` desde HubSpot | Solo esquema + documentación; snapshot en refresh futuro |
