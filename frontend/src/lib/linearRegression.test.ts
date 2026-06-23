import { describe, expect, it } from 'vitest'
import { addWeeklyTrendLine, linearRegression } from '@/lib/linearRegression'

describe('linearRegression', () => {
  it('fits a perfect line', () => {
    const points = [
      { x: 0, y: 2 },
      { x: 1, y: 4 },
      { x: 2, y: 6 },
    ]
    const { slope, intercept } = linearRegression(points)
    expect(slope).toBeCloseTo(2)
    expect(intercept).toBeCloseTo(2)
  })

  it('excludes last week from trend fit by default', () => {
    const data = [
      { week_start: '2026-01-05', calls: 10 },
      { week_start: '2026-01-12', calls: 20 },
      { week_start: '2026-01-19', calls: 30 },
      { week_start: '2026-01-26', calls: 999 },
    ]
    const withTrend = addWeeklyTrendLine(data, 'calls')
    expect(withTrend[0].trend).toBe(10)
    expect(withTrend[1].trend).toBe(20)
    expect(withTrend[2].trend).toBe(30)
    expect(withTrend[3].trend).toBe(40)
  })
})
