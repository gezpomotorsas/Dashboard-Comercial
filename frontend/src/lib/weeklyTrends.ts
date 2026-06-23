/** Tendencias semanales híbridas por tipo de serie (EMA, suma móvil, mediana móvil). */

export const MIN_WEEKS_FOR_TREND = 6
export const EMA_SPAN = 4
export const ROLLING_WINDOW = 4

export type TrendMethod = 'ema' | 'rolling_sum' | 'rolling_median'

export type PeriodChange = {
  changePct: number | null
  label: string
}

export function emaSeries(values: number[], span: number = EMA_SPAN): (number | null)[] {
  if (values.length === 0) return []
  const alpha = 2 / (span + 1)
  const result: (number | null)[] = []
  let prev: number | null = null

  for (let i = 0; i < values.length; i++) {
    const value = values[i]
    if (prev === null) {
      prev = value
      result.push(Math.round(value))
      continue
    }
    prev = alpha * value + (1 - alpha) * prev
    result.push(Math.round(prev))
  }
  return result
}

export function rollingSumSeries(values: number[], window: number = ROLLING_WINDOW): (number | null)[] {
  return values.map((_, index) => {
    if (index + 1 < window) return null
    const slice = values.slice(index - window + 1, index + 1)
    return Math.round(slice.reduce((sum, value) => sum + value, 0))
  })
}

export function rollingMedianSeries(values: number[], window: number = ROLLING_WINDOW): (number | null)[] {
  return values.map((_, index) => {
    if (index + 1 < window) return null
    const sorted = [...values.slice(index - window + 1, index + 1)].sort((a, b) => a - b)
    const mid = Math.floor(sorted.length / 2)
    if (sorted.length % 2 === 1) {
      return sorted[mid]
    }
    return Math.round((sorted[mid - 1] + sorted[mid]) / 2)
  })
}

/** Compara suma de las últimas N semanas vs las N anteriores. */
export function periodOverPeriodChange(values: number[], window: number = ROLLING_WINDOW): PeriodChange {
  if (values.length < window * 2) {
    return { changePct: null, label: '' }
  }

  const recent = values.slice(-window).reduce((sum, value) => sum + value, 0)
  const previous = values.slice(-window * 2, -window).reduce((sum, value) => sum + value, 0)

  if (previous === 0) {
    if (recent === 0) {
      return { changePct: 0, label: 'Sin cambio vs 4 sem anteriores' }
    }
    return { changePct: null, label: 'Al alza vs 4 sem anteriores (base previa en 0)' }
  }

  const changePct = Math.round(((recent - previous) / previous) * 1000) / 10
  const sign = changePct > 0 ? '+' : ''
  return {
    changePct,
    label: `${sign}${changePct}% vs 4 sem anteriores`,
  }
}

export function trendSeriesForMethod(values: number[], method: TrendMethod): (number | null)[] {
  switch (method) {
    case 'ema':
      return emaSeries(values)
    case 'rolling_sum':
      return rollingSumSeries(values)
    case 'rolling_median':
      return rollingMedianSeries(values)
  }
}

export function trendLegendLabel(method: TrendMethod): string {
  switch (method) {
    case 'ema':
      return 'Tendencia EMA (4 sem)'
    case 'rolling_sum':
      return 'Suma móvil 4 sem'
    case 'rolling_median':
      return 'Mediana móvil 4 sem'
  }
}

export function trendDescriptionSuffix(method: TrendMethod, periodLabel: string): string {
  const base =
    method === 'ema'
      ? 'Línea punteada = media móvil exponencial (4 semanas), tendencia orientativa'
      : method === 'rolling_sum'
        ? 'Línea punteada = suma móvil de 4 semanas (ritmo reciente de cierres)'
        : 'Línea punteada = mediana móvil de 4 semanas (montos, robusta a outliers)'

  if (!periodLabel) return base
  return `${base} · ${periodLabel}`
}

export function addWeeklyTrend<T extends Record<string, unknown>>(
  data: T[],
  valueKey: keyof T & string,
  method: TrendMethod,
  options?: {
    trendKey?: string
    minWeeks?: number
  },
): Array<T & Record<string, number | null>> {
  const trendKey = options?.trendKey ?? 'trend'
  const minWeeks = options?.minWeeks ?? MIN_WEEKS_FOR_TREND
  const values = data.map((row) => Number(row[valueKey]) || 0)

  const trendValues =
    data.length >= minWeeks ? trendSeriesForMethod(values, method) : data.map(() => null)

  return data.map((row, index) => ({
    ...row,
    [trendKey]: trendValues[index],
  }))
}

export function enrichClosedWeeklySeries<
  T extends { deals_closed: number; total_amount: number; week_start: string },
>(rows: T[]): Array<
  T & {
    count_trend: number | null
    amount_trend: number | null
  }
> {
  const counts = rows.map((row) => row.deals_closed)
  const amounts = rows.map((row) => row.total_amount)

  const countTrend =
    rows.length >= MIN_WEEKS_FOR_TREND ? rollingSumSeries(counts) : rows.map(() => null)
  const amountTrend =
    rows.length >= MIN_WEEKS_FOR_TREND ? rollingMedianSeries(amounts) : rows.map(() => null)

  return rows.map((row, index) => ({
    ...row,
    count_trend: countTrend[index],
    amount_trend: amountTrend[index],
  }))
}
