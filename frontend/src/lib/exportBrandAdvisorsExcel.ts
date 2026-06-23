import * as XLSX from 'xlsx'
import type { QueryClient } from '@tanstack/react-query'
import { fetchBrandOperating } from '@/api/brandOperating'
import { cachedQueryDefaults } from '@/lib/queryDefaults'
import { staleThresholdDays } from '@/lib/brandStale'
import { buildBrandAdvisorTableColumns } from '@/lib/brandAdvisorTableColumns'
import {
  advisorToExportRow,
  channelMixRows,
  flattenContactMethodology,
  keyValueRows,
  mergeWeeklyTrendRows,
  monthlySummaryColumns,
  distributionRows,
} from '@/lib/exportBrandExcelHelpers'
import { BRAND_KPI_TOOLTIPS } from '@/lib/metricTooltips'
import type { OperatingBrand } from '@/hooks/useBrandOperating'
import type { BrandOperatingData, DealAnalyticsEnvelope } from '@/types/dealAnalytics'

const BRANDS: OperatingBrand[] = ['voyah', 'mhero', 'shacman']

function methodologyRows(
  brand: OperatingBrand,
  brandLabel: string,
  generatedAt: string,
  staleDays: number,
  envelope: DealAnalyticsEnvelope<BrandOperatingData>,
): Record<string, string>[] {
  const rows: Record<string, string>[] = [
    { Sección: 'Marca', Detalle: brandLabel },
    {
      Sección: 'Propósito',
      Detalle:
        `Exportación analítica completa de la marca ${brandLabel}. ` +
        'Incluye cartera, contacto, ventas, rendimiento mensual, tendencias y metodología. ' +
        'Diseñado para análisis en Excel o herramientas de IA.',
    },
    { Sección: 'Generado', Detalle: generatedAt },
    { Sección: 'Zona horaria', Detalle: envelope.timezone },
    { Sección: 'Estancados — umbral (días)', Detalle: String(staleDays) },
    {
      Sección: 'Población',
      Detalle: `${envelope.population.included_deals} incluidos / ${envelope.population.total_deals} totales`,
    },
    {
      Sección: 'Calidad de datos',
      Detalle: `${envelope.data_quality.status} — ${envelope.data_quality.notes.join('; ') || 'sin notas'}`,
    },
    {
      Sección: 'Nota actividades',
      Detalle: envelope.data.activity_coverage_note ?? '—',
    },
    {
      Sección: 'Metodología contacto',
      Detalle:
        'Cobertura = negocios activos contactados (llamada y/o WhatsApp) en ventana de contacto (21 días) ÷ negocios activos. ' +
        '«Sin llamada ni WhatsApp 21d» = elegibles sin contacto por esos canales. ' +
        'Estancados: 21 días (Voyah/MHero) o 45 días (Shacman) sin actividad sincronizada.',
    },
    {
      Sección: 'Hojas del archivo',
      Detalle:
        'Resumen, Ventas, Contacto, Mix canales, Asesores, Tendencias semanales, Etapas, Llamadas por día/hora, WhatsApp por día.',
    },
  ]

  for (const [kpi, tip] of Object.entries(BRAND_KPI_TOOLTIPS)) {
    rows.push({ Sección: `KPI: ${kpi}`, Detalle: tip })
  }

  for (const col of buildBrandAdvisorTableColumns(brand, staleDays)) {
    rows.push({ Sección: `Columna asesores: ${col.label}`, Detalle: col.tooltip })
  }

  return rows
}

function brandSummaryMetrics(
  envelope: DealAnalyticsEnvelope<BrandOperatingData>,
  staleDays: number,
): Record<string, string | number | null> {
  const data = envelope.data
  const summary = data.contact_methodology?.brand_summary

  return {
    Marca: data.brand_label,
    'Código marca': data.brand_value,
    'Umbral estancados (días)': staleDays,
    'Total negocios': data.totals.all_deals,
    Abiertos: data.totals.open_deals,
    Ganados: data.totals.won_deals,
    Perdidos: data.totals.lost_deals,
    [`Estancados ${staleDays}d (abiertos)`]: data.totals.stale_45d_open,
    'Nuevos 7 días': data.totals.new_deals_7d,
    'Nuevos 30 días': data.totals.new_deals_30d,
    'Ventana contacto (días)': data.contact_methodology?.contact_window_days ?? null,
    'Generado (API)': envelope.generated_at,
    ...monthlySummaryColumns('Ventas unidades (marca)', data.won_sales_summary),
    ...flattenContactMethodology(summary),
  }
}

function stageRows(
  envelope: DealAnalyticsEnvelope<BrandOperatingData>,
  staleDays: number,
): Record<string, string | number>[] {
  const rows: Record<string, string | number>[] = []
  for (const group of envelope.data.stage_groups) {
    rows.push({
      'Grupo comercial': group.commercial_group_label,
      Abiertos: group.open_deals,
      [`Estancados ${staleDays}d`]: group.stale_45d,
      'Con tareas vencidas': group.with_overdue_tasks,
    })
    for (const stage of group.stages_detail) {
      rows.push({
        'Grupo comercial': group.commercial_group_label,
        Etapa: stage.stage_label,
        Negocios: stage.count,
      })
    }
  }
  return rows
}

async function loadBrandEnvelope(
  queryClient: QueryClient,
  brand: OperatingBrand,
): Promise<DealAnalyticsEnvelope<BrandOperatingData>> {
  return queryClient.fetchQuery({
    queryKey: ['brand-operating', brand],
    queryFn: () => fetchBrandOperating(brand),
    ...cachedQueryDefaults,
  })
}

function sheetFromJson<T extends object>(rows: T[]): XLSX.WorkSheet {
  return XLSX.utils.json_to_sheet(rows, { skipHeader: false })
}

function appendSheet(wb: XLSX.WorkBook, ws: XLSX.WorkSheet, name: string) {
  XLSX.utils.book_append_sheet(wb, ws, name.slice(0, 31))
}

function downloadWorkbook(wb: XLSX.WorkBook, filename: string) {
  XLSX.writeFile(wb, filename, { bookType: 'xlsx', compression: true })
}

function slugifyBrand(brand: OperatingBrand, brandLabel: string): string {
  return brand || brandLabel.toLowerCase().replace(/\s+/g, '-')
}

function buildBrandWorkbook(
  envelope: DealAnalyticsEnvelope<BrandOperatingData>,
  brand: OperatingBrand,
  generatedAt: string,
): XLSX.WorkBook {
  const data = envelope.data
  const brandLabel = data.brand_label
  const staleDays = staleThresholdDays(brand, data.stale_threshold_days)
  const summary = data.contact_methodology?.brand_summary

  const advisorRows = data.advisors
    .map((row) => advisorToExportRow(row, staleDays))
    .sort((a, b) => Number(b.Abiertos ?? 0) - Number(a.Abiertos ?? 0))

  const wb = XLSX.utils.book_new()
  appendSheet(
    wb,
    sheetFromJson(methodologyRows(brand, brandLabel, generatedAt, staleDays, envelope)),
    'Metodología',
  )
  appendSheet(wb, sheetFromJson(keyValueRows(brandSummaryMetrics(envelope, staleDays))), 'Resumen marca')
  appendSheet(
    wb,
    sheetFromJson(keyValueRows(monthlySummaryColumns('Ventas unidades', data.won_sales_summary))),
    'Ventas marca',
  )
  appendSheet(wb, sheetFromJson(keyValueRows(flattenContactMethodology(summary))), 'Contacto marca')

  const mixRows = channelMixRows(summary)
  if (mixRows.length > 0) {
    appendSheet(wb, sheetFromJson(mixRows), 'Mix canales')
  }

  appendSheet(wb, sheetFromJson(advisorRows), 'Asesores')

  const weeklyRows = mergeWeeklyTrendRows({
    weekly_created: data.weekly_created,
    weekly_won: data.weekly_won,
    weekly_lost: data.weekly_lost,
    weekly_calls: data.weekly_calls,
  })
  if (weeklyRows.length > 0) {
    appendSheet(wb, sheetFromJson(weeklyRows), 'Tendencias semanales')
  }

  const stageDetailRows = stageRows(envelope, staleDays)
  if (stageDetailRows.length > 0) {
    appendSheet(wb, sheetFromJson(stageDetailRows), 'Etapas')
  }

  const callWeekday = distributionRows(
    summary?.calls?.by_weekday?.map((r) => ({ label: r.weekday, count: r.count })),
    'Día',
    'Llamadas',
  )
  if (callWeekday.length > 0) {
    appendSheet(wb, sheetFromJson(callWeekday), 'Llamadas por día')
  }

  const callTime = (summary?.calls?.by_time_band ?? []).map((r) => ({
    Franja: r.time_band,
    Llamadas: r.calls,
    'Negocios únicos': r.unique_deals,
    'Minutos totales': r.total_minutes ?? null,
    'Tasa conexión (%)': r.connected_rate ?? null,
  }))
  if (callTime.length > 0) {
    appendSheet(wb, sheetFromJson(callTime), 'Llamadas por hora')
  }

  const callDuration = (summary?.calls?.duration_ranges ?? []).map((r) => ({
    Rango: r.range,
    Llamadas: r.count,
  }))
  if (callDuration.length > 0) {
    appendSheet(wb, sheetFromJson(callDuration), 'Duración llamadas')
  }

  const waWeekday = distributionRows(
    summary?.whatsapp?.by_weekday?.map((r) => ({ label: r.weekday, count: r.count })),
    'Día',
    'Mensajes',
  )
  if (waWeekday.length > 0) {
    appendSheet(wb, sheetFromJson(waWeekday), 'WhatsApp por día')
  }

  return wb
}

/** Exporta un Excel analítico completo para la marca indicada. */
export async function exportBrandAdvisorsExcel(
  queryClient: QueryClient,
  brand: OperatingBrand,
): Promise<void> {
  const envelope = await loadBrandEnvelope(queryClient, brand)
  const generatedAt = new Date().toISOString()
  const wb = buildBrandWorkbook(envelope, brand, generatedAt)
  const datePart = generatedAt.slice(0, 10)
  const slug = slugifyBrand(brand, envelope.data.brand_label)
  downloadWorkbook(wb, `analitica-${slug}-${datePart}.xlsx`)
}

/** Exporta las tres marcas en archivos separados (uno por marca). */
export async function exportAllBrandsExcel(queryClient: QueryClient): Promise<void> {
  const generatedAt = new Date().toISOString()
  const datePart = generatedAt.slice(0, 10)

  for (const brand of BRANDS) {
    const envelope = await loadBrandEnvelope(queryClient, brand)
    const wb = buildBrandWorkbook(envelope, brand, generatedAt)
    const slug = slugifyBrand(brand, envelope.data.brand_label)
    downloadWorkbook(wb, `analitica-${slug}-${datePart}.xlsx`)
  }
}
