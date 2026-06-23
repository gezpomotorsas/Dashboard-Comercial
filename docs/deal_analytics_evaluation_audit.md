# Auditoría de evaluación — Deal Analytics (Fase 1)

Fecha: 2026-06-20  
Alcance: código real vs documentación vs requisitos de metodología v2.

---

## 1. Fórmulas reales encontradas

### 1.1 `discipline_contact_score` — `contact_metrics.py:762-777`

```
25% × call_coverage_rate
25% × whatsapp_coverage_rate
25% × combined_coverage_rate
15% × (100 − overdue_contact_21d_rate)
10% × combined_coverage_rate   ← DUPLICACIÓN
```

**Problema matemático:** `overdue_contact_21d_rate = 100 − combined_coverage_rate` (negocios sin llamada ni WA en ventana). Por tanto el término `15% × combined` + `10% × combined` + componentes de call/wa que correlacionan → **cobertura combinada contada ~2×**.

### 1.2 `effectiveness_commercial_score` (capa contacto) — `contact_metrics.py:441-443`

`= close_rate` puro (`won / (won+lost)`).

### 1.3 `discipline_score` (vista global asesores) — `query.py:1637-1646`

```
35% × managed_30d_rate
35% × effective_contact_30d_rate
15% × (100 − % negocios con tareas vencidas)
15% × (100 − % desatendidos)
```

### 1.4 `effectiveness_score` (vista global) — `query.py:1649-1655`

```
70% × close_rate
30% × min(100, won_amount / open_pipeline × 10)   ← sesgo cartera pequeña
```

### 1.5 Clasificación de llamadas — dos reglas distintas

| Función | Archivo | Regla |
|---------|---------|-------|
| `is_call_effective` | `hubspot_configuration/store.py:459` | status COMPLETED o outcome no negativo |
| `classify_call_connection` | `contact_metrics.py:102` | outcome → disposition → **duration > 0 → connected** |

**Problema:** llamada de 1s sin outcome cuenta como conectada en contact_metrics.

### 1.6 Tareas en negocios cerrados — `builder.py:149-157`

`_empty_task_stats()` → todos los contadores de tareas en **0** en refresh. Destruye hechos históricos.

### 1.7 Atribución de llamadas

| Métrica | Resolución |
|---------|------------|
| `load_contact_activity_bundle` | Solo deal→actividad |
| `_weekly_calls_for_deals` | deal→actividad + contacto→llamada |
| Portfolio weekly trend | Solo bundle deal→actividad |

**Problema:** mismas llamadas contadas distinto según vista; posible duplicación en gráfica semanal (sin dedup por activity_id).

### 1.8 Historial de propietario

**No existe.** Solo `hubspot_owner_id` actual + inferencia desde actividades.

---

## 2. Diferencias documentación vs código

| Tema | Doc | Código |
|------|-----|--------|
| Gráfica llamadas portfolio | deal+contacto | Solo deal (weekly_trend del bundle) |
| Tareas cerrados | Excluidas de operación | Ceros en deal_analytics |
| Efectividad contacto | ≈ close_rate | Igual |
| Comunicaciones efectivas | WhatsApp en contact_metrics | Builder: toda communication es efectiva |
| Owner history | No documentado | No implementado |

---

## 3. Fuentes por KPI

| KPI | Tablas / props |
|-----|----------------|
| Cobertura llamadas | `hubspot_calls`, `hubspot_associations`, `deal_analytics` |
| Atrasados 21d | Última llamada/WA por negocio en ventana |
| Tareas vencidas | `hubspot_tasks`, `hs_task_due_date`, `hs_task_status` |
| Gestión 30d | Actividades sync 60d en refresh |
| Estancamiento | `days_since_last_activity`, `days_in_current_stage` |
| Primera respuesta | `created_at` → primer contacto efectivo (no asignación) |

---

## 4. Dependencias frontend

| Componente | Campos críticos |
|------------|-----------------|
| `BrandOperatingPage` | `discipline_contact_score`, `overdue_contact_21d` |
| `AdvisorPortfolioPage` | `summary.discipline_contact_score`, task_counts |
| `ContactMethodologySection` | `evaluation.discipline_contact_score` |
| `DealAnalyticsPage` | `discipline_score`, `effectiveness_score` |
| `metricTooltips.ts` | Labels «Disciplina», «Atrasados 21d» |

---

## 5. Migraciones necesarias

1. `deal_owner_history` — historial de asignación (fallback desde owner actual).
2. Columnas `deal_analytics`: `historical_*` y `operational_*` tareas; campos de elegibilidad y próxima acción (JSON o columnas).
3. Índices en `deal_owner_history(deal_id, owner_id, assigned_from)`.

---

## 6. Plan de implementación por archivos

| Fase | Archivos nuevos | Archivos modificados |
|------|-----------------|----------------------|
| 2-3 | `operational_scores.py`, `evaluation_config.py` | `contact_metrics.py`, `query.py`, tipos TS |
| 4 | `contact_classification.py` | `contact_metrics.py`, `builder.py` |
| 5 | `contact_eligibility.py` | `contact_metrics.py`, `operational_scores.py` |
| 6-7 | `first_response.py` | `builder.py`, `evaluation_config.py` |
| 8 | `sql/010_*.sql`, `owner_history.py` | `refresh.py` |
| 9 | `activity_attribution.py` | `contact_metrics.py`, `query.py`, `repository` |
| 12 | — | `builder.py`, `refresh.py` |
| 13-14 | `next_action.py`, `risk_dimensions.py` | `builder.py`, `query.py` |
| 15-16 | `evaluation_metadata.py`, `activity_origin.py` | `query.py` API envelope |
| 17 | — | `metricTooltips.ts`, componentes React |
| 18 | `tests/test_evaluation_methodology_v2.py` | tests existentes |
| 20 | `docs/deal_analytics_evaluation_methodology_v2.md`, `migration_v2.md` | `METRICAS_ANALITICA.md` |

---

## 7. Decisiones conservadoras (sin datos HubSpot adicionales)

- Elegibilidad: excluir solo lo inferible (`closed`, `missing_owner`, `non_actionable_stage` vía commercial_group).
- Pausas / do-not-contact: configurables pero `unknown` hasta mapear propiedades.
- Owner assignment: fallback a `created_at` con `attribution_status=partial`.
- WhatsApp entrante/saliente: `unknown` si HubSpot no expone dirección.
- Festivos: no implementados; documentar limitación.

---

*Auditoría generada como prerequisito de implementación v2. Continuar con código sin gate de aprobación.*
