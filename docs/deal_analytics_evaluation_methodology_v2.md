# Metodología de evaluación comercial v2

Documento de negocio para interpretar el dashboard tras la refactorización de medición (2026-06).

---

## 1. Qué mide el sistema (8 capas)

| Capa | Qué es | Ejemplos en UI |
|------|--------|----------------|
| Actividad registrada | Cualquier sync en HubSpot | `activity_count`, volumen de llamadas |
| Intento de contacto | Salida válida sin confirmar respuesta | Llamada saliente, WA saliente |
| Contacto logrado | Evidencia de conexión | `connected_calls`, outcome CONNECTED |
| Contacto significativo | Conversación comercial plausible | Duración ≥30s + señal, o outcome claro |
| Cumplimiento operativo | SLA, próxima acción, tareas | **Disciplina operativa** |
| Avance comercial | Movimiento de etapa, progresión | `progression_status` |
| Resultado comercial | Cierres en cohortes maduras | **Efectividad comercial** |
| Calidad de dato | available / partial / insufficient | Badges, `evaluation_metadata` |

---

## 2. Qué NO mide (evitar malinterpretaciones)

- **Sin llamada ni WhatsApp en 21 días** ≠ tareas vencidas ≠ negocio desatendido.
- **Cobertura de llamadas** ≠ minutos en teléfono (requiere `hs_call_duration`).
- **Disciplina operativa** ≠ volumen bruto de actividades.
- **Efectividad comercial** con muestra &lt; 3 cierres → `insufficient`; no usar para sancionar.
- Actividades **automáticas/workflow** no mejoran disciplina humana (cuando origen es `unknown`, se documenta).

---

## 3. Negocios elegibles

Solo los negocios **elegibles** entran en denominadores de cumplimiento SLA.

**Elegible:** abierto, con propietario, contacto, etapa accionable.

**Excluidos (ejemplos):** cerrado, sin owner, etapa de cierre, prueba/duplicado, pausa futura (`paused_until`), do-not-contact (si está configurado).

La API expone: `total_open_deals`, `eligible_deals`, `excluded_deals`, `excluded_by_reason`.

---

## 4. Disciplina operativa (nuevo score principal de contacto)

Componentes **independientes** (pesos por defecto):

| Componente | Peso | Definición |
|------------|------|------------|
| Cumplimiento contacto elegible | 30% | % elegibles contactados dentro del SLA de seguimiento por etapa |
| Primera respuesta SLA | 25% | % con primera gestión dentro del SLA desde **asignación** (fallback: creación) |
| Próxima acción | 20% | % con tarea futura válida no vencida |
| Contacto efectivo | 15% | % con contacto significativo (no solo intento) |
| Cumplimiento tareas | 10% | % elegibles sin tareas pendientes vencidas |

**Status:** `available`, `partial` (faltan componentes), `insufficient` (menos de 3 componentes con dato).

**Legacy:** `legacy_discipline_contact_score` conserva la fórmula antigua (duplicaba cobertura combinada).

---

## 5. Disciplina integral de gestión

Antes columna **«Disciplina»** en vista global de asesores.

Combina gestión 30d, contacto efectivo 30d, tareas vencidas y desatención.  
Campo API: `management_discipline_score` (alias `discipline_score`).

---

## 6. Efectividad comercial

- **Nuevo:** `commercial_effectiveness_score` basado en conversión de cohorte con mínimo de cierres.
- **Legacy:** `legacy_effectiveness_commercial_score` = tasa de cierre simple.
- **Deprecated component:** `won_amount / open_pipeline` solo como fallback en vista global antigua.

---

## 7. Clasificación de llamadas (taxonomía única)

Prioridad: outcome → disposition → status → duración (conservadora).

- 0–5 s sin outcome → `unknown`, no conectada automáticamente.
- `NO_ANSWER`, `BUSY`, etc. → nunca conectada por duración.
- `COMPLETED` en HubSpot → conectada con confianza media (alineado a telefonía integrada).

Conteos en UI: conectadas / no conectadas / indeterminadas + badge de confianza.

---

## 8. Atribución actividad → negocio

Orden: asociación directa deal → contacto con único negocio abierto → match por owner → `ambiguous`.

Una misma llamada **no se duplica** entre negocios. Métricas de calidad: `attributed_activity_count`, `ambiguous_activity_count`, `duplicate_prevented_count`.

Cobertura y gráficas semanales usan el **mismo resolvedor**.

---

## 9. Tareas: histórico vs operativo

| Campo | Uso |
|-------|-----|
| `historical_*_task_count` | Hechos reales, incluso en negocios cerrados |
| `operational_*` | KPIs de gestión actual; cerados en cierre ganado/perdido |

---

## 10. Periodos y muestras

Toda tasa de efectividad debe mostrar numerador, denominador, `sample_size`, `data_status`.

Ranking principal excluye asesores con `minimum_sample_met = false` (config: 5 negocios, 3 cierres para efectividad).

---

## 11. Limitaciones conocidas

- Historial de propietario: tabla `deal_owner_history` con snapshot parcial; sin `propertiesWithHistory` de owner en sync actual → primera respuesta usa creación como fallback (`data_status=partial`).
- Festivos no modelados en minutos hábiles.
- WhatsApp: dirección entrante/saliente a menudo `unknown`.
- Pausas y do-not-contact: requieren mapear propiedades HubSpot adicionales.

---

## 12. Cómo usar para coaching

1. Mirar **disciplina operativa** con desglose de componentes, no un solo número.
2. Verificar **elegibilidad** antes de comparar coberturas entre asesores.
3. Usar **Sin llamada ni WhatsApp en 21d** solo para canal, no como único indicador de riesgo.
4. Revisar `risk_priority` y `risk_reasons` en explorador (sin doble contar la misma causa).
5. No premiar o sancionar con `insufficient` en efectividad.

---

Ver también: `docs/deal_analytics_migration_v2.md`, `docs/deal_analytics_evaluation_audit.md`.
