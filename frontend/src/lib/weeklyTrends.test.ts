import { describe, expect, it } from 'vitest'
import {
  addWeeklyTrend,
  emaSeries,
  enrichClosedWeeklySeries,
  MIN_WEEKS_FOR_TREND,
  periodOverPeriodChange,
  rollingMedianSeries,
  rollingSumSeries,
} from '@/lib/weeklyTrends'

describe('weeklyTrends', () => {
  it('calcula EMA suavizada', () => {
    const ema = emaSeries([10, 20, 30, 40])
    expect(ema[0]).toBe(10)
    expect(ema[1]).toBeGreaterThan(10)
    expect(ema[3]).toBeGreaterThan(ema[2]!)
  })

  it('calcula suma móvil de 4 semanas', () => {
    const sums = rollingSumSeries([1, 2, 3, 4, 5])
    expect(sums[2]).toBeNull()
    expect(sums[3]).toBe(10)
    expect(sums[4]).toBe(14)
  })

  it('calcula mediana móvil de 4 semanas', () => {
    const medians = rollingMedianSeries([1, 100, 2, 3, 4])
    expect(medians[3]).toBe(3)
  })

  it('compara periodos de 4 semanas', () => {
    const values = [1, 1, 1, 1, 2, 2, 2, 2]
    const change = periodOverPeriodChange(values)
    expect(change.changePct).toBe(100)
    expect(change.label).toContain('+100%')
  })

  it('oculta tendencia EMA con pocas semanas', () => {
    const data = Array.from({ length: MIN_WEEKS_FOR_TREND - 1 }, (_, i) => ({
      week_start: `2026-01-${String(i + 1).padStart(2, '0')}`,
      calls: i + 1,
    }))
    const enriched = addWeeklyTrend(data, 'calls', 'ema')
    expect(enriched.every((row) => row.trend === null)).toBe(true)
  })

  it('enriquece cierres con suma móvil y mediana', () => {
    const rows = Array.from({ length: MIN_WEEKS_FOR_TREND }, (_, i) => ({
      week_start: `2026-01-${String(i + 1).padStart(2, '0')}`,
      deals_closed: i + 1,
      total_amount: (i + 1) * 1_000_000,
    }))
    const enriched = enrichClosedWeeklySeries(rows)
    expect(enriched[5]?.count_trend).not.toBeNull()
    expect(enriched[5]?.amount_trend).not.toBeNull()
  })
})
