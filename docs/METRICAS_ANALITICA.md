# Documentación de métricas — Deal Analytics

Guía de referencia del dashboard comercial (Gezpomotor HubSpot Extractor). Describe **qué mide cada KPI**, **de dónde salen los datos**, **cómo se calcula** y **para qué sirve** en la gestión.

---

## 1. Arquitectura general

### Flujo de datos

```
HubSpot API
    → Sync incremental (Supabase)
        hubspot_deals, hubspot_calls, hubspot_tasks, hubspot_communications, …
        hubspot_associations (contacto↔negocio, negocio↔actividad, contacto↔llamada)
    → Builder (deal_analytics refresh)
        Tabla deal_analytics — una fila por negocio con KPIs precalculados
    → Query API (tiempo casi real)
        Agregaciones por marca, asesor, grupo + métricas de contacto (llamadas/WhatsApp)
    → Frontend React
```

### Dos capas de métricas

| Capa | Origen | Uso principal |
|------|--------|---------------|
| **deal_analytics** | Refresh batch (`scripts/run_deal_analytics_refresh.py`) | Gestión de negocio, tareas, actividad general, estancamiento |
| **contact_metrics** | Cálculo en API al consultar marca/asesor/grupo | Cobertura de llamadas y WhatsApp, disciplina de contacto |

### Población y filtros

- Por defecto muchas vistas filtran **negocios abiertos** (`status = open`).
- **Marca** (`voyah`, `mhero`, `shacman`) se resuelve desde pipeline, propiedades del negocio o mapeos en `hubspot_configuration`.
- **Asesor** = `hubspot_owner_id` del negocio (o inferido desde actividades si falta).
- La tabla `deal_analytics` refleja el estado en el momento del último refresh; la API de contacto usa actividades en Supabase al vuelo.

---

## 2. Configuración relevante (variables de entorno)

| Variable | Default | Efecto en métricas |
|----------|---------|-------------------|
| `ACTIVITY_SYNC_LOOKBACK_DAYS` | 60 | Solo se sincronizan actividades de los últimos N días. Sin historial más antiguo en BD. |
| `CONTACT_COVERAGE_WINDOW_DAYS` | 21 | Ventana para cobertura de llamadas/WhatsApp y «Atrasados 21d». |
| `WHATSAPP_SESSION_GAP_HOURS` | 24 | Gap entre mensajes para estimar una «sesión» de WhatsApp. |
| `STALE_DEAL_DAYS_WITHOUT_ACTIVITY` | 30 | Días sin actividad para marcar negocio **estancado** (`is_stale`). |
| `STALE_DEAL_DAYS_IN_STAGE` | 30 | Días en la etapa actual para contribuir a estancamiento. |
| `BUSINESS_TIMEZONE` | `America/Bogota` | Agrupación semanal, franjas horarias, semanas en gráficas. |
| `TASK_SYNC_FULL_HISTORY` | `true` | Tareas: historial completo en sync full (no limitado a 60 días). |

---

## 3. Objetos y propiedades HubSpot usadas

### Negocios (`deals`)

| Concepto | Propiedades típicas |
|----------|---------------------|
| Nombre | `dealname` |
| Etapa | `dealstage` |
| Pipeline | `pipeline` |
| Monto | `amount` |
| Propietario | `hubspot_owner_id` |
| Creación | `createdate` |
| Cierre | `closedate` |
| Estado | Resuelto vía `hubspot_configuration` (ganado/perdido/abierto) |

### Llamadas (`calls`)

| Propiedad | Uso |
|-----------|-----|
| `hs_timestamp` | Fecha/hora de la llamada |
| `hs_call_duration` | Duración (ms o s; normalizada a segundos) |
| `hs_call_outcome`, `hs_call_disposition`, `hs_call_status` | Conexión y llamada «efectiva» |
| `hs_call_direction` | Entrante / saliente |
| `hubspot_owner_id` | Asesor que registró la llamada |

### WhatsApp (`communications`)

| Propiedad | Uso |
|-----------|-----|
| `hs_timestamp` | Fecha del mensaje |
| `hs_communication_channel_type` | Debe ser `WHATS_APP` |
| `hubspot_owner_id` | Asesor asociado |

### Tareas (`tasks`)

| Propiedad | Uso |
|-----------|-----|
| `hs_task_subject` | Asunto; detecta «Perdiste este Lead» |
| `hs_task_status` | Pendiente vs completada |
| `hs_task_due_date` | Vencimiento |
| `hs_task_priority` | Prioridad en tabla de cartera |
| `hubspot_owner_id` | Asesor responsable |

### Asociaciones (`hubspot_associations`)

- **Negocio ↔ contacto**: cartera y zona.
- **Negocio ↔ actividad**: tareas, llamadas, comunicaciones en refresh de negocio.
- **Contacto ↔ llamada**: usado en gráfica semanal de llamadas (no en cobertura estándar; ver §12).

---

## 4. Métricas por negocio (`deal_analytics` / builder)

Cada fila se construye en `app/services/deal_analytics/builder.py` agregando actividades asociadas al negocio.

### 4.1 Identidad y dimensiones

| Métrica | Datos | Qué muestra | Objetivo |
|---------|-------|-------------|----------|
| `deal_name`, `deal_id` | HubSpot | Identificación | Navegación |
| `brand_value` / `brand_label` | Pipeline + mapeos | Marca comercial | Segmentar Voyah / MHero / Shacman |
| `zone_value` / `zone_label` | Negocio o contacto | Zona territorial | Análisis geográfico |
| `stage_label`, `commercial_group` | Etapa HubSpot + semántica | Etapa y grupo comercial (prospección, cotización, cierre…) | Embudo y concentración de cartera |
| `owner_id` / `owner_name` | `hubspot_owner_id` | Asesor asignado | Rendimiento por persona |
| `status` | Config HubSpot | `open` / `won` / `lost` | Población activa vs cerrada |
| `amount` | `amount` | Valor del negocio (COP) | Pipeline y efectividad |

### 4.2 Tiempo y antigüedad

| Métrica | Cálculo | Objetivo |
|---------|---------|----------|
| `age_days` | Días desde `created_at` hasta hoy | Antigüedad del lead |
| `days_in_current_stage` | Desde última entrada a etapa actual (historial) | Detectar estancamiento en etapa |
| `days_since_last_activity` | Desde última actividad sincronizada (cualquier tipo) | Inactividad general |
| `days_since_effective_contact` | Desde último contacto efectivo | Calidad de seguimiento comercial |
| `first_response_minutes` | Creación del negocio → primer contacto efectivo | Velocidad de primera respuesta |

**Contacto efectivo** = llamada con `is_call_effective`, comunicación (WhatsApp/email sync), o reunión completada.  
**No cuenta**: tareas ni notas como contacto efectivo en esta capa.

**Llamada efectiva** (`is_call_effective`):

- `hs_call_status` ∈ {`COMPLETED`, `COMPLETE`}, o
- `hs_call_outcome` presente y no ∈ {`NO_ANSWER`, `BUSY`, `FAILED`, `CANCELED`, `CANCELLED`}.

### 4.3 Conteos de actividad (asociadas al negocio en refresh)

| Métrica | Incluye | Objetivo |
|---------|---------|----------|
| `activity_count` | Llamadas, comunicaciones, reuniones, notas | Volumen total de interacción |
| `call_count` | Llamadas | Intensidad telefónica |
| `completed_call_count` | Llamadas efectivas | Llamadas con señal de conexión |
| `communication_count` | Comunicaciones sync | Mensajes (incl. WhatsApp) |
| `meeting_count` / `completed_meeting_count` | Reuniones | Citas y reuniones hechas |
| `note_count` | Notas | Registro interno |
| `task_count` | Tareas (excl. «Perdiste este Lead») | Carga de gestión |
| `open_task_count` | Tareas no completadas | Pendientes |
| `completed_task_count` | Tareas completadas | Ejecución |
| `overdue_task_count` | Tareas **pendientes** con `due_date < hoy` | Backlog vencido |
| `has_overdue_tasks` | `overdue_task_count > 0` | Señal de riesgo |
| `tasks_due_next_7d` | Pendientes que vencen en 7 días | Planificación inmediata |
| `oldest_overdue_task_days` | Máximo días de atraso en tareas pendientes | Gravedad del atraso |

**Tareas en negocios ganados/perdidos**: `task_count`, `overdue_task_count`, etc. se ponen en **0** en `deal_analytics` (no afectan KPIs de gestión). Las **llamadas sí siguen contando**.

### 4.4 Flags de gestión y riesgo

| Métrica | Condición | Objetivo |
|---------|-----------|----------|
| `has_recent_activity_30d` | Alguna actividad en últimos 30 días | «¿Se está trabajando el negocio?» |
| `has_recent_effective_contact_30d` | Contacto efectivo en 30 días | «¿Hubo contacto real con el cliente?» |
| `is_stale_45d` | Abierto y (sin actividad **o** ≥45 días sin actividad) | Alerta rápida de abandono |
| `is_stale` | Abierto y (sin actividad ≥30d **o** ≥30d en etapa) | Estancamiento configurable |
| `stale_reason` | `no_recent_activity`, `too_long_in_stage`, `both` | Diagnóstico |
| `is_unattended` | Abierto y cumple ≥1 criterio abajo | Negocio desatendido |
| `unattended_reason` | Ver tabla siguiente | Priorización |

**Criterios de desatención** (`_unattended_status`):

1. Sin actividad en 30 días  
2. Sin contacto efectivo en 30 días  
3. Tiene tareas vencidas pendientes  
4. Sin tarea futura programada (vencimiento >7 días o sin fecha)

Si varios aplican → `multiple_reasons`.

| Métrica | Objetivo |
|---------|----------|
| `alert_reason` | Combina estancamiento + desatención para explorador |
| `data_completeness_score` | % de campos clave poblados (owner, contacto, monto, actividad…) |

---

## 5. Métricas de contacto — Llamadas y WhatsApp (Etapa 2)

Calculadas en `app/services/deal_analytics/contact_metrics.py` al consultar marca, asesor o grupo.  
Centradas en **negocios abiertos** del alcance filtrado.

### 5.1 Resolución de actividades

1. Se cargan llamadas y comunicaciones **asociadas directamente al negocio** (`load_contact_activity_bundle`).
2. WhatsApp: solo registros con `hs_communication_channel_type = WHATS_APP`.
3. Se filtran por `owner_id` del asesor cuando aplica (propietario de la actividad o del negocio).
4. **Ventana de cobertura**: actividades con timestamp ≥ `hoy − CONTACT_COVERAGE_WINDOW_DAYS` (default 21).

### 5.2 Cobertura (KPIs principales del encabezado)

| Métrica | Fórmula | Qué muestra | Objetivo |
|---------|---------|-------------|----------|
| **Cobertura llamadas** (`call_coverage_rate`) | Negocios activos con ≥1 llamada en ventana ÷ activos | % cartera llamada recientemente | Disciplina de prospección telefónica |
| **Cobertura WhatsApp** (`whatsapp_coverage_rate`) | Negocios activos con ≥1 WhatsApp en ventana ÷ activos | % cartera con mensajería | Disciplina digital |
| **Cobertura combinada** (`combined_contact_coverage_rate`) | Negocios con llamada **y/o** WhatsApp en ventana ÷ activos | Contacto por cualquier canal | Vista unificada de seguimiento |
| **Atrasados 21d** (`overdue_contact_21d`) | Negocios activos **sin** llamada **ni** WhatsApp en 21 días (conteo absoluto) | Cartera sin contacto reciente | Identificar negocios olvidados |
| **Atrasados 21d %** (`overdue_contact_21d_rate`) | `overdue_contact_21d ÷ activos × 100` | Proporción | Alimenta índice de disciplina |

**Importante**: «Atrasados 21d» **no** son tareas vencidas. Son negocios sin **llamada ni WhatsApp** en la ventana. Tareas, reuniones o emails **no** evitan este contador.

Numeradores en UI: `call_coverage_numerator / call_coverage_denominator` (ej. `1/100 neg.`).

### 5.3 Métricas de llamadas (detalle)

| Métrica | Descripción | Objetivo |
|---------|-------------|----------|
| `total_calls` | Llamadas asociadas al alcance (histórico en bundle, no solo ventana) | Volumen |
| `outbound_calls` / `inbound_calls` | Por `hs_call_direction` | Perfil de llamadas |
| `connected_calls` | `call_connection = connected` (outcome/disposition/duración) | Calidad de conexión |
| `unanswered_calls` | Outcomes tipo NO_ANSWER, BUSY… | Esfuerzo sin contacto |
| `unique_deals_called` | Negocios distintos con llamada **en ventana** | Cobertura (numerador) |
| `deals_called_last_7d/21d/30d` | Negocios con llamada en esos períodos | Recencia |
| `total_call_minutes` | Suma de duraciones válidas | Tiempo en teléfono |
| `median_call_duration_seconds` | Mediana de duración | Perfil de conversación |
| `duration_data_status` | `available` / `partial` / `insufficient` / `unavailable` | Calidad del dato `hs_call_duration` |
| `duration_ranges` | Histograma por rangos (0s, 1–30s, …) | Distribución de duración |
| `by_weekday` / `by_time_band` | Llamadas por día y franja horaria | Patrones de trabajo |
| `weekly_trend` | Serie semanal de conteo | Tendencia |

**Conexión de llamada** (`classify_call_connection`):

1. `hs_call_outcome` / `hs_call_disposition`  
2. Si no hay señal: duración > 0 → conectada  
3. Si no: `unknown`

### 5.4 Métricas de WhatsApp

| Métrica | Descripción | Objetivo |
|---------|-------------|----------|
| `whatsapp_messages` | Mensajes en alcance | Volumen |
| `unique_deals_with_whatsapp` | Negocios con WhatsApp en ventana | Cobertura WA |
| `estimated_whatsapp_sessions` | Mensajes agrupados por negocio; nueva sesión si gap > 24h | Aproximar conversaciones |
| `average_messages_per_session` | Mensajes ÷ sesiones | Intensidad por conversación |
| `session_estimation_warning` | Aviso de que es estimación | Transparencia de dato |

HubSpot **no** expone ID de conversación ni duración de chat; las sesiones son heurística.

### 5.5 Mix de canales (`channel_mix`)

Clasifica cada negocio activo en la ventana:

| Clase | Condición |
|-------|-----------|
| Sin gestión reciente | Ni llamada ni WhatsApp en ventana |
| Solo llamada | Llamada sí, WhatsApp no |
| Solo WhatsApp | WhatsApp sí, llamada no |
| Multicanal | Ambos |

**Objetivo**: ver dependencia de un solo canal y brechas de contacto.

### 5.6 Índices de evaluación (contacto)

#### Disciplina de contacto (`discipline_contact_score`, 0–100)

```
25% × cobertura llamadas
25% × cobertura WhatsApp
25% × cobertura combinada
15% × (100 − % atrasados 21d)
10% × cobertura combinada (refuerzo)
```

**Objetivo**: medir **constancia de contacto** a la cartera, no volumen bruto ni cierres.

#### Efectividad comercial (`effectiveness_commercial_score`)

En esta capa ≈ **tasa de cierre** (`won ÷ (won + lost)`) cuando hay negocios cerrados.

**Objetivo**: resultados comerciales del asesor/grupo.

#### Clasificación de carga (`load_classification`)

| Texto | Condición |
|-------|-----------|
| Carga alta, gestión saludable | ≥40 negocios activos y cobertura ≥50% y atrasados <30% |
| Carga alta, cobertura baja | ≥40 activos y no saludable |
| Carga normal, cobertura baja | <40 activos y no saludable |
| Carga normal, gestión saludable | Resto |

**Objetivo**: contextualizar KPIs según tamaño de cartera.

---

## 6. Índices compuestos — Vista «Asesores» global

En `query.py` → `_discipline_score` / `_effectiveness_score` (tabla comparativa de asesores, distinto del score de contacto).

### Disciplina (gestión integral, 0–100)

```
35% × Gestión 30d (% abiertos con actividad en 30d)
35% × Contacto 30d (% abiertos con contacto efectivo en 30d)
15% × (100 − penalización tareas vencidas)
15% × (100 − penalización desatendidos)
```

Penalizaciones = % de negocios abiertos con tareas vencidas / desatendidos (cap 100).

### Efectividad (0–100)

```
70% × tasa de cierre
30% × min(100, won_amount / open_pipeline × 10)
```

### Estado de gestión (`management_status`)

| Estado | Condición |
|--------|-----------|
| Gestión saludable | Disciplina ≥70 y efectividad ≥50 |
| Cartera en riesgo | Disciplina <50 o efectividad <30 |
| Requiere seguimiento | Intermedio |
| Información insuficiente | Sin datos para calcular |

---

## 7. Métricas por vista del frontend

### 7.1 Resumen global (`DealAnalyticsPage` → Resumen)

| KPI | Fuente | Objetivo |
|-----|--------|----------|
| Total / abiertos / ganados / perdidos | `deal_analytics` agregado | Panorama de cartera |
| Pipeline abierto / ganado | Suma `amount` | Valor comercial |
| Estancados | `is_stale` | Riesgo de abandono |
| Desatendidos (abiertos) | `is_unattended` | Intervención urgente |
| Con tareas vencidas | `has_overdue_tasks` en abiertos | Backlog por negocio |
| Gestión 30d / Contacto 30d | Flags de 30 días | Salud operativa |
| Distribución por estado | Conteo por `status` | Composición |

### 7.2 Operación por marca (`BrandOperatingPage`)

| Sección | Métricas | Objetivo |
|---------|----------|----------|
| KPIs superiores | Abiertos, nuevos 7d/30d, estancados 45d, coberturas, atrasados 21d | Salud de la marca |
| Grupos de etapa | Abiertos por grupo comercial, estancados 45d, con tareas vencidas | Embudo operativo |
| Tabla asesores | Abiertos, nuevos, estancados, tareas, coberturas, disciplina/efectividad | Ranking por persona |
| Gráficas semanales | Creados, ganados, perdidos, **llamadas** (+ línea de tendencia) | Evolución temporal |
| Metodología de contacto | Bloque `ContactMethodologySection` | Detalle llamadas/WA |

**Gráfica semanal de llamadas**: usa asociación **negocio→llamada** y **contacto→llamada** (más completa que cobertura estándar).

### 7.3 Cartera del asesor (`AdvisorPortfolioPage`)

| KPI / bloque | Descripción | Objetivo |
|--------------|-------------|----------|
| Negocios asignados | Todos los negocios del asesor en la marca | Tamaño histórico de cartera |
| Abiertos | Solo `is_open` | Carga actual |
| Coberturas y atrasados 21d | Igual que §5.2 | Disciplina de contacto |
| `ContactMethodologySection` | KPIs, gráficas y duración | Análisis profundo de contacto |
| Gráficas de cartera | Creados semanales, inactividad, etapas | Diagnóstico de cartera |
| **Tabla de tareas** | Tareas del asesor vinculadas a contacto o negocio | Operación diaria |

#### Filtros de tareas (cartera)

| Filtro | Lógica | Objetivo |
|--------|--------|----------|
| Todas | Sin filtro de estado | Vista completa |
| Pendientes | `is_completed = false` | Trabajo por hacer |
| Vencidas | Pendiente y `due_at < hoy` | **Acción urgente** (métrica operativa) |
| Completadas atrasadas | Completada y `due_at < hoy` | Histórico de cierre tarde (no penaliza «vencidas») |
| Completadas | `is_completed = true` | Ejecutado |

#### Exclusiones en tabla de tareas

| Tipo | Regla |
|------|-------|
| Huérfanas | Sin asociación a contacto **ni** negocio |
| «Perdiste este Lead» | Asunto contiene texto de reasignación; no cuenta en rendimiento |
| Negocio en cierre | Ganado/perdido o grupo `cierre_ganado` / `cierre_perdido` |

Contadores expuestos: `excluded_orphan`, `excluded_reassigned_lead`, `excluded_closed_deal`.

### 7.4 Grupos de asesores (`GrupoPage`)

- Agrega métricas de asesores miembros **desde registros base** (no promedio de promedios).
- `rollup_group_contact_metrics` recalcula cobertura sobre todos los negocios del grupo.
- Comparativas: cobertura, atrasados, tareas, disciplina entre grupos.

### 7.5 Embudo, marcas×zonas, explorador

| Vista | Métricas clave | Objetivo |
|-------|----------------|----------|
| Embudo | Por etapa: total, abiertos, ganados, perdidos, estancados | Conversión por etapa |
| Marcas y zonas | Pipeline, gestión 30d, contacto 30d, desatendidos, tasa cierre | Segmentación territorial |
| Asesores (comparativa) | Disciplina, efectividad, estado, tasas | Ranking y coaching |
| Explorador | Negocios ordenables con alertas | Investigación caso a caso |

---

## 8. Gráficas y series temporales

| Serie | Agrupación | Fuente de fecha |
|-------|------------|-----------------|
| `weekly_created` | Semana (lunes) | `created_at` del negocio |
| `weekly_won` / `weekly_lost` | Semana | `closed_at` |
| `weekly_calls` | Semana | `hs_timestamp` de llamadas |
| `weekly_overdue_tasks` | Semana del vencimiento | `hs_task_due_date` de tareas **pendientes** vencidas |
| Tendencia lineal (marca) | Regresión sobre semanas de llamadas | Excluye última semana incompleta |

Zona horaria: `BUSINESS_TIMEZONE` (default Bogotá).

---

## 9. Tareas vencidas — Dos definiciones distintas

| Concepto | Nivel | Definición |
|----------|-------|------------|
| **Tareas vencidas** | Tarea / asesor | Cada tarea **pendiente** con fecha de vencimiento pasada |
| **Neg. c/ tareas venc.** | Negocio | Negocios abiertos con ≥1 tarea vencida pendiente (máx. 1 por negocio) |
| **Atrasados 21d** | Negocio (contacto) | Sin llamada **ni** WhatsApp en 21 días |

No confundir «tareas vencidas» con «atrasados 21d».

---

## 10. Reglas especiales de negocio

### «Perdiste este Lead»

- Tarea de workflow cuando el lead se reasigna a otro asesor.
- **Excluida** de: agregación de tareas en `deal_analytics`, portfolio del asesor, gráfica semanal de vencidas.
- **No excluida** de otras actividades del negocio.

### Negocios en cierre ganado/perdido

- Métricas de **tareas** en `deal_analytics` → ceradas para esos negocios.
- En portfolio: tareas de esos negocios no aparecen en la tabla.
- **Llamadas y WhatsApp** siguen contando para contacto e historial.

### Llamada efectiva vs conectada

- **Efectiva** (builder): status/outcome HubSpot.
- **Conectada** (contact_metrics): lógica ampliada con duración y disposición.

---

## 11. Calidad y limitaciones de datos

| Tema | Impacto |
|------|---------|
| Ventana sync 60 días | `days_since_last_activity` puede ser `null` o bajo si la última actividad fue hace >60 días y no está en BD |
| `hs_call_duration` vacío | Duración y minutos no disponibles; usar conteos y cobertura |
| Cobertura vs gráfica de llamadas | Cobertura usa solo asociación **negocio→llamada**; gráfica semanal también **contacto→llamada** → la gráfica puede mostrar más llamadas que la cobertura |
| WhatsApp | Sin duración; sesiones estimadas |
| Refresh `deal_analytics` | KPIs de tareas/estancamiento en vista marca requieren refresh reciente para exclusiones de cierre |
| Caché API | `brand_operating` y `advisor_portfolio` ~5 min (`_RESPONSE_CACHE_TTL_SECONDS`) |

---

## 12. Referencia rápida — ¿Qué mirar para…?

| Pregunta de negocio | Métrica recomendada |
|---------------------|---------------------|
| ¿Están llamando a la cartera? | Cobertura llamadas, `weekly_calls` |
| ¿Están usando WhatsApp? | Cobertura WhatsApp, sesiones estimadas |
| ¿Qué negocios no han sido contactados? | Atrasados 21d, mix «Sin gestión reciente» |
| ¿Quién tiene tareas atrasadas pendientes? | Tareas vencidas (filtro), `tasks_overdue` |
| ¿Quién cerró tarde pero ya completó? | Completadas atrasadas (filtro aparte) |
| ¿Qué negocios están abandonados? | `is_stale_45d`, desatendidos, días sin actividad |
| ¿Quién convierte mejor? | Tasa de cierre, efectividad comercial |
| ¿Quién gestiona con disciplina? | Disciplina de contacto, disciplina (vista asesores) |
| ¿Cuánto tiempo en llamada? | `total_call_minutes`, `median_call_duration_seconds` (si hay duración) |

---

## 13. Archivos de código de referencia

| Área | Archivo |
|------|---------|
| Construcción por negocio | `app/services/deal_analytics/builder.py` |
| Métricas llamadas/WhatsApp | `app/services/deal_analytics/contact_metrics.py` |
| API y agregaciones | `app/services/deal_analytics/query.py` |
| Semántica de tareas | `app/services/deal_analytics/task_semantics.py` |
| Tooltips UI | `frontend/src/lib/metricTooltips.ts` |
| Configuración | `app/config.py` |
| Refresh batch | `scripts/run_deal_analytics_refresh.py` |

---

*Última actualización: alineada con la separación de tareas «Vencidas» vs «Completadas atrasadas» en cartera de asesor y metodología de contacto v2.*
