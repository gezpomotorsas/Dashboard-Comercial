import { describe, expect, it } from 'vitest'
import {
  formatMonthKey,
  formatMonthOverMonthDisplay,
  formatMonthOverMonthLabel,
} from '@/lib/wonSalesSummary'
import type { WonSalesSummary } from '@/types/dealAnalytics'

describe('wonSalesSummary', () => {
  it('formats month keys in Spanish', () => {
    expect(formatMonthKey('2026-06')).toMatch(/junio/i)
    expect(formatMonthKey('2026-05')).toMatch(/mayo/i)
  })

  it('formats month-over-month increase', () => {
    const summary: WonSalesSummary = {
      total_units: 100,
      units_this_month: 15,
      units_previous_month: 10,
      month_over_month_change_pct: 50,
      this_month_key: '2026-06',
      previous_month_key: '2026-05',
    }
    expect(formatMonthOverMonthLabel(summary)).toContain('junio')
    expect(formatMonthOverMonthLabel(summary)).toContain('mayo')
    expect(formatMonthOverMonthDisplay(summary).secondary).toMatch(/junio.*vs.*mayo/i)
  })

  it('handles zero previous month base', () => {
    const summary: WonSalesSummary = {
      total_units: 5,
      units_this_month: 3,
      units_previous_month: 0,
      month_over_month_change_pct: null,
      this_month_key: '2026-06',
      previous_month_key: '2026-05',
    }
    expect(formatMonthOverMonthDisplay(summary).primary).toBe('↑ Nuevo')
    expect(formatMonthOverMonthDisplay(summary).secondary).toMatch(/junio.*vs.*mayo/i)
  })
})
