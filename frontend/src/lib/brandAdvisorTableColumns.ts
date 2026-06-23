import type { MetricColumn } from '@/lib/metricTooltips'
import { BRAND_ADVISOR_COLUMNS } from '@/lib/metricTooltips'
import { staleMetricShortLabel, staleMetricTooltip } from '@/lib/brandStale'

/** Columnas de la tabla de asesores con agrupación y espaciado optimizado. */
export function buildBrandAdvisorTableColumns(brand: string, staleDays?: number): MetricColumn[] {
  const staleShort = staleMetricShortLabel(brand, staleDays)

  return BRAND_ADVISOR_COLUMNS.map((col) => {
    const column =
      col.label === 'Estanc. 45d'
        ? { ...col, label: staleShort, tooltip: staleMetricTooltip(brand, staleDays) }
        : col

    switch (column.label) {
      case 'Asesor':
        return { ...column, sticky: true, minWidth: 160 }
      case 'Abiertos':
      case 'Nuevos 7d':
      case 'Nuevos 30d':
      case staleShort:
        return { ...column, group: 'Cartera' as const, align: 'right' as const, minWidth: 88 }
      case 'Tareas hechas':
      case 'Tareas abiertas':
      case 'Tareas vencidas':
      case 'Neg. c/ tareas venc.':
        return { ...column, group: 'Tareas' as const, align: 'right' as const, minWidth: 96 }
      case 'Gestión 30d':
      case 'Cob. llamadas':
      case 'Cob. WhatsApp':
      case 'Cob. combinada':
      case 'Atrasados 21d':
        return { ...column, group: 'Contacto' as const, align: 'right' as const, minWidth: 96 }
      case 'Ventas totales':
      case 'Ventas este mes':
        return { ...column, group: 'Ventas' as const, align: 'right' as const, minWidth: 96 }
      case 'Cambio mensual':
        return { ...column, group: 'Ventas' as const, align: 'center' as const, minWidth: 120 }
      default:
        return column
    }
  })
}

/** @deprecated Usar buildBrandAdvisorTableColumns(brand) para etiquetas por marca. */
export const BRAND_ADVISOR_TABLE_COLUMNS = buildBrandAdvisorTableColumns('shacman')
