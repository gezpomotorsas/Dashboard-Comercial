import { describe, expect, it } from 'vitest'
import {
  advisorToExportRow,
  flattenContactMethodology,
  mergeWeeklyTrendRows,
  monthlySummaryColumns,
} from '@/lib/exportBrandExcelHelpers'
import type { BrandAdvisorRow } from '@/types/dealAnalytics'

function sampleAdvisorRow(): BrandAdvisorRow {
  return {
    owner_id: '123',
    owner_name: 'Ana Pérez',
    brand_value: 'voyah',
    assigned_deals: 50,
    open_deals: 30,
    new_deals_7d: 2,
    new_deals_30d: 8,
    stale_45d_open: 4,
    tasks_completed: 20,
    tasks_open: 5,
    tasks_overdue: 3,
    deals_with_overdue_tasks: 2,
    managed_30d: 25,
    managed_30d_rate: 83.3,
    tasks_overdue_rate: 10.5,
    call_coverage_rate: 70,
    whatsapp_coverage_rate: 60,
    combined_coverage_rate: 80,
    overdue_contact_21d: 5,
    discipline_contact_score: 72,
    effectiveness_commercial_score: 65,
    won_sales: {
      total_units: 56,
      units_this_month: 8,
      units_previous_month: 6,
      month_over_month_change_pct: 33.3,
      this_month_key: '2026-06',
      previous_month_key: '2026-05',
    },
    performance: {
      won_sales: {
        total_units: 56,
        units_this_month: 8,
        units_previous_month: 6,
        month_over_month_change_pct: 33.3,
        this_month_key: '2026-06',
        previous_month_key: '2026-05',
      },
      leads_created: {
        total_units: 120,
        units_this_month: 18,
        units_previous_month: 15,
        month_over_month_change_pct: 20,
        this_month_key: '2026-06',
        previous_month_key: '2026-05',
      },
      tasks_overdue: 3,
      tasks_overdue_monthly: {
        total_units: 10,
        units_this_month: 3,
        units_previous_month: 4,
        month_over_month_change_pct: -25,
        this_month_key: '2026-06',
        previous_month_key: '2026-05',
      },
      tasks_completed_monthly: {
        total_units: 20,
        units_this_month: 5,
        units_previous_month: 4,
        month_over_month_change_pct: 25,
        this_month_key: '2026-06',
        previous_month_key: '2026-05',
      },
      tasks_managed_monthly: {
        total_units: 30,
        units_this_month: 8,
        units_previous_month: 7,
        month_over_month_change_pct: 14.3,
        this_month_key: '2026-06',
        previous_month_key: '2026-05',
      },
      calls_monthly: {
        total_units: 200,
        units_this_month: 45,
        units_previous_month: 40,
        month_over_month_change_pct: 12.5,
        this_month_key: '2026-06',
        previous_month_key: '2026-05',
      },
      whatsapp_monthly: {
        total_units: 150,
        units_this_month: 30,
        units_previous_month: 28,
        month_over_month_change_pct: 7.1,
        this_month_key: '2026-06',
        previous_month_key: '2026-05',
      },
    },
  }
}

describe('exportBrandExcelHelpers', () => {
  it('incluye ventas y rendimiento mensual en fila de asesor', () => {
    const exported = advisorToExportRow(sampleAdvisorRow(), 21)
    expect(exported.Asesor).toBe('Ana Pérez')
    expect(exported['Ventas (unidades) — total histórico']).toBe(56)
    expect(exported['Leads creados — mes actual (2026-06)']).toBe(18)
    expect(exported['Llamadas — mes actual (2026-06)']).toBe(45)
  })

  it('aplana métricas de contacto de marca', () => {
    const flat = flattenContactMethodology({
      active_deals: 40,
      calls: { total_calls: 100, unique_deals_called: 30, call_coverage_rate: 75 },
      whatsapp: { whatsapp_messages: 200, unique_deals_with_whatsapp: 25, whatsapp_coverage_rate: 62.5 },
      coverage: { combined_contact_coverage_rate: 80, deals_multichannel: 10 },
      evaluation: { discipline_operational_score: 13.3, load_classification: 'Carga alta, cobertura baja' },
    })
    expect(flat['Llamadas — total']).toBe(100)
    expect(flat['Evaluación — disciplina operativa']).toBe(13.3)
  })

  it('combina tendencias semanales en una tabla', () => {
    const rows = mergeWeeklyTrendRows({
      weekly_created: [{ week_start: '2026-06-02', deals_created: 5 }],
      weekly_won: [{ week_start: '2026-06-02', deals_closed: 2, total_amount: 1000000 }],
      weekly_lost: [{ week_start: '2026-06-02', deals_closed: 1, total_amount: 500000 }],
      weekly_calls: [{ week_start: '2026-06-02', calls: 40 }],
    })
    expect(rows).toHaveLength(1)
    expect(rows[0]['Negocios creados']).toBe(5)
    expect(rows[0].Llamadas).toBe(40)
  })

  it('genera columnas de resumen mensual', () => {
    const cols = monthlySummaryColumns('Ventas', {
      total_units: 10,
      units_this_month: 3,
      units_previous_month: 2,
      month_over_month_change_pct: 50,
      this_month_key: '2026-06',
      previous_month_key: '2026-05',
    })
    expect(cols['Ventas — cambio mensual (%)']).toBe(50)
  })
})
