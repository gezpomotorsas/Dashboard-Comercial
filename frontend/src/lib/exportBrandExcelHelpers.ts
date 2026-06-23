import type { GroupPerformanceMetrics } from '@/types/advisorGroups'
import type { ContactMethodologyData } from '@/types/contactMetrics'
import type { BrandAdvisorRow, WonSalesSummary } from '@/types/dealAnalytics'

export type ExportScalar = string | number | null

export function num(value: number | null | undefined): number | null {
  if (value == null || Number.isNaN(value)) return null
  return value
}

export function pct(value: number | null | undefined): number | null {
  const n = num(value)
  return n == null ? null : Math.round(n * 10) / 10
}

export function monthlySummaryColumns(
  prefix: string,
  summary?: WonSalesSummary | null,
): Record<string, ExportScalar> {
  if (!summary) {
    return {
      [`${prefix} — total histórico`]: null,
      [`${prefix} — mes actual`]: null,
      [`${prefix} — mes anterior`]: null,
      [`${prefix} — cambio mensual (%)`]: null,
    }
  }
  return {
    [`${prefix} — total histórico`]: summary.total_units,
    [`${prefix} — mes actual (${summary.this_month_key})`]: summary.units_this_month,
    [`${prefix} — mes anterior (${summary.previous_month_key})`]: summary.units_previous_month,
    [`${prefix} — cambio mensual (%)`]: pct(summary.month_over_month_change_pct),
  }
}

export function performanceColumns(
  performance?: GroupPerformanceMetrics | null,
): Record<string, ExportScalar> {
  if (!performance) return {}
  return {
    ...monthlySummaryColumns('Ventas (unidades)', performance.won_sales),
    ...monthlySummaryColumns('Leads creados', performance.leads_created),
    'Tareas vencidas (actual)': num(performance.tasks_overdue),
    ...monthlySummaryColumns('Tareas vencidas', performance.tasks_overdue_monthly),
    ...monthlySummaryColumns('Tareas completadas', performance.tasks_completed_monthly),
    ...monthlySummaryColumns('Tareas gestionadas', performance.tasks_managed_monthly),
    ...monthlySummaryColumns('Llamadas', performance.calls_monthly),
    ...monthlySummaryColumns('WhatsApp', performance.whatsapp_monthly),
  }
}

export function flattenContactMethodology(
  metrics?: ContactMethodologyData | null,
): Record<string, ExportScalar> {
  if (!metrics) return {}
  const calls = metrics.calls
  const wa = metrics.whatsapp
  const cov = metrics.coverage
  const ev = metrics.evaluation

  return {
    'Contacto — negocios activos': num(metrics.active_deals),
    'Contacto — negocios asignados': num(metrics.assigned_deals),
    'Contacto — ganados': num(metrics.won_deals),
    'Contacto — tasa cierre (%)': pct(metrics.close_rate),
    'Contacto — ventana (días)': num(metrics.contact_window_days),
    'Llamadas — total': num(calls?.total_calls),
    'Llamadas — salientes': num(calls?.outbound_calls),
    'Llamadas — entrantes': num(calls?.inbound_calls),
    'Llamadas — conectadas': num(calls?.connected_calls),
    'Llamadas — no contestadas': num(calls?.unanswered_calls),
    'Llamadas — negocios únicos': num(calls?.unique_deals_called),
    'Llamadas — cobertura (%)': pct(calls?.call_coverage_rate),
    'Llamadas — cobertura num/den': `${calls?.call_coverage_numerator ?? '—'}/${calls?.call_coverage_denominator ?? '—'}`,
    'Llamadas — minutos totales': num(calls?.total_call_minutes),
    'Llamadas — duración media (seg)': num(calls?.average_call_duration_seconds),
    'Llamadas — duración mediana (seg)': num(calls?.median_call_duration_seconds),
    'Llamadas — calidad dato duración': calls?.duration_data_status ?? null,
    'Llamadas — negocios sin llamada': num(calls?.deals_without_calls),
    'Llamadas — negocios 7d': num(calls?.deals_called_last_7d),
    'Llamadas — negocios 21d': num(calls?.deals_called_last_21d),
    'Llamadas — negocios 30d': num(calls?.deals_called_last_30d),
    'WhatsApp — mensajes': num(wa?.whatsapp_messages),
    'WhatsApp — negocios únicos': num(wa?.unique_deals_with_whatsapp),
    'WhatsApp — cobertura (%)': pct(wa?.whatsapp_coverage_rate),
    'WhatsApp — cobertura num/den': `${wa?.whatsapp_coverage_numerator ?? '—'}/${wa?.whatsapp_coverage_denominator ?? '—'}`,
    'WhatsApp — sesiones estimadas': num(wa?.estimated_whatsapp_sessions),
    'WhatsApp — msg/sesión promedio': num(wa?.average_messages_per_session),
    'WhatsApp — msg/negocio promedio': num(wa?.messages_per_deal_average),
    'WhatsApp — negocios 7d': num(wa?.deals_with_whatsapp_7d),
    'WhatsApp — negocios 21d': num(wa?.deals_with_whatsapp_21d),
    'WhatsApp — negocios 30d': num(wa?.deals_with_whatsapp_30d),
    'Cobertura — combinada (%)': pct(cov?.combined_contact_coverage_rate),
    'Cobertura — combinada num/den': `${cov?.combined_contact_coverage_numerator ?? '—'}/${cov?.combined_contact_coverage_denominator ?? '—'}`,
    'Cobertura — sin gestión reciente': num(cov?.deals_no_recent_contact),
    'Cobertura — solo llamada': num(cov?.deals_call_only),
    'Cobertura — solo WhatsApp': num(cov?.deals_whatsapp_only),
    'Cobertura — multicanal': num(cov?.deals_multichannel),
    'Cobertura — sin llamada ni WA 21d': num(cov?.channel_overdue_21d ?? cov?.overdue_contact_21d),
    'Cobertura — sin llamada ni WA 21d (%)': pct(cov?.channel_overdue_21d_rate ?? cov?.overdue_contact_21d_rate),
    'Evaluación — disciplina operativa': num(ev?.discipline_operational_score),
    'Evaluación — estado disciplina': ev?.discipline_operational_status ?? null,
    'Evaluación — disciplina legacy': num(ev?.legacy_discipline_contact_score),
    'Evaluación — efectividad comercial': num(ev?.commercial_effectiveness_score ?? ev?.effectiveness_commercial_score),
    'Evaluación — estado efectividad': ev?.commercial_effectiveness_status ?? null,
    'Evaluación — clasificación carga': ev?.load_classification ?? null,
    'Evaluación — alerta carga 40+': ev?.load_alert_40_plus == null ? null : ev.load_alert_40_plus ? 'Sí' : 'No',
  }
}

export function keyValueRows(data: Record<string, ExportScalar>): Array<{ Métrica: string; Valor: ExportScalar }> {
  return Object.entries(data).map(([Métrica, Valor]) => ({ Métrica, Valor }))
}

export function advisorToExportRow(row: BrandAdvisorRow, staleDays: number): Record<string, ExportScalar> {
  const cm = row.contact_metrics

  return {
    Marca: row.brand_value,
    Asesor: row.owner_name ?? 'Sin asignar',
    'ID asesor HubSpot': row.owner_id ?? '',
    'Negocios asignados': row.assigned_deals,
    Abiertos: row.open_deals,
    'Nuevos 7 días': row.new_deals_7d,
    'Nuevos 30 días': row.new_deals_30d,
    [`Estancados ${staleDays}d (abiertos)`]: row.stale_45d_open,
    'Tareas completadas': row.tasks_completed,
    'Tareas abiertas': row.tasks_open,
    'Tareas vencidas': row.tasks_overdue,
    'Negocios con tareas vencidas': row.deals_with_overdue_tasks,
    'Tasa tareas vencidas (%)': pct(row.tasks_overdue_rate),
    'Gestión 30d (%)': pct(row.managed_30d_rate),
    'Negocios gestionados 30d': row.managed_30d,
    'Cobertura llamadas (%)': pct(row.call_coverage_rate),
    'Cobertura WhatsApp (%)': pct(row.whatsapp_coverage_rate),
    'Cobertura combinada (%)': pct(row.combined_coverage_rate),
    'Sin llamada ni WhatsApp 21d': num(row.channel_overdue_21d ?? row.overdue_contact_21d),
    'Sin llamada ni WhatsApp 21d (%)': pct(row.channel_overdue_21d_rate ?? row.overdue_contact_21d_rate),
    'Total llamadas (ventana)': num(row.total_calls),
    'Negocios únicos llamados': num(row.unique_deals_called),
    'Minutos totales llamadas': num(row.total_call_minutes),
    'Duración mediana llamada (seg)': num(row.median_call_duration_seconds),
    'Calidad datos duración': row.duration_data_status ?? null,
    'Mensajes WhatsApp': num(row.whatsapp_messages),
    'Negocios con WhatsApp': num(row.unique_deals_with_whatsapp),
    'Sesiones WhatsApp (estimadas)': num(row.estimated_whatsapp_sessions),
    'Disciplina operativa (0-100)': num(row.discipline_operational_score ?? row.discipline_contact_score),
    'Estado disciplina operativa': row.discipline_operational_status ?? null,
    'Disciplina contacto legacy (0-100)': num(row.legacy_discipline_contact_score),
    'Efectividad comercial (0-100)': num(row.effectiveness_commercial_score ?? row.commercial_effectiveness_score),
    'Clasificación de carga': row.load_classification ?? null,
    'Negocios ganados': num(cm?.won_deals),
    'Tasa de cierre (%)': pct(row.close_rate ?? cm?.close_rate),
    ...(row.performance
      ? performanceColumns(row.performance)
      : {
          ...monthlySummaryColumns('Ventas unidades', row.won_sales),
          ...monthlySummaryColumns('Leads creados', row.leads_created),
        }),
    ...flattenContactMethodology(cm),
  }
}

export function channelMixRows(
  metrics?: ContactMethodologyData | null,
): Array<{ Canal: string; Negocios: number }> {
  const mix = metrics?.coverage?.channel_mix
  if (!mix) return []
  return Object.entries(mix).map(([Canal, Negocios]) => ({ Canal, Negocios: Number(Negocios) || 0 }))
}

export interface WeeklyTrendInput {
  weekly_created: Array<{ week_start: string; deals_created: number }>
  weekly_won: Array<{ week_start: string; deals_closed: number; total_amount: number }>
  weekly_lost: Array<{ week_start: string; deals_closed: number; total_amount: number }>
  weekly_calls?: Array<{ week_start: string; calls: number }>
}

export function mergeWeeklyTrendRows(input: WeeklyTrendInput): Array<Record<string, ExportScalar>> {
  const weeks = new Set<string>()
  for (const row of input.weekly_created) weeks.add(row.week_start)
  for (const row of input.weekly_won) weeks.add(row.week_start)
  for (const row of input.weekly_lost) weeks.add(row.week_start)
  for (const row of input.weekly_calls ?? []) weeks.add(row.week_start)

  const created = new Map(input.weekly_created.map((r) => [r.week_start, r.deals_created]))
  const won = new Map(input.weekly_won.map((r) => [r.week_start, r]))
  const lost = new Map(input.weekly_lost.map((r) => [r.week_start, r]))
  const calls = new Map((input.weekly_calls ?? []).map((r) => [r.week_start, r.calls]))

  return Array.from(weeks)
    .sort()
    .map((week) => {
      const w = won.get(week)
      const l = lost.get(week)
      return {
        Semana: week,
        'Negocios creados': created.get(week) ?? 0,
        'Cierres ganados': w?.deals_closed ?? 0,
        'Monto ganado (COP)': w?.total_amount ?? 0,
        'Cierres perdidos': l?.deals_closed ?? 0,
        'Monto perdido (COP)': l?.total_amount ?? 0,
        Llamadas: calls.get(week) ?? 0,
      }
    })
}

export function distributionRows(
  items: Array<{ label: string; count: number }> | undefined,
  labelKey: string,
  valueKey: string,
): Array<Record<string, ExportScalar>> {
  if (!items?.length) return []
  return items.map((item) => ({ [labelKey]: item.label, [valueKey]: item.count }))
}
