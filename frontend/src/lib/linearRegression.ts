export interface LinearRegressionResult {
  slope: number
  intercept: number
}

/** Regresión lineal simple por mínimos cuadrados (y = slope·x + intercept). */
export function linearRegression(points: Array<{ x: number; y: number }>): LinearRegressionResult {
  const n = points.length
  if (n === 0) {
    return { slope: 0, intercept: 0 }
  }
  if (n === 1) {
    return { slope: 0, intercept: points[0].y }
  }
  let sumX = 0
  let sumY = 0
  let sumXY = 0
  let sumXX = 0
  for (const { x, y } of points) {
    sumX += x
    sumY += y
    sumXY += x * y
    sumXX += x * x
  }
  const denom = n * sumXX - sumX * sumX
  if (denom === 0) {
    return { slope: 0, intercept: sumY / n }
  }
  const slope = (n * sumXY - sumX * sumY) / denom
  const intercept = (sumY - slope * sumX) / n
  return { slope, intercept }
}

/**
 * Añade campo `trend` a cada semana. Por defecto excluye la última semana del ajuste
 * (suele estar incompleta).
 */
export function addWeeklyTrendLine<T extends Record<string, unknown>>(
  data: T[],
  valueKey: keyof T & string,
  options?: { excludeLastWeek?: boolean; trendKey?: string },
): Array<T & Record<string, number | null>> {
  const trendKey = options?.trendKey ?? 'trend'
  if (data.length < 2) {
    return data.map((row) => ({ ...row, [trendKey]: null }))
  }

  const excludeLast = options?.excludeLastWeek !== false
  const fitRows = excludeLast && data.length > 1 ? data.slice(0, -1) : data
  const points = fitRows.map((row, index) => ({
    x: index,
    y: Number(row[valueKey]) || 0,
  }))
  const { slope, intercept } = linearRegression(points)

  return data.map((row, index) => ({
    ...row,
    [trendKey]: Math.round(slope * index + intercept),
  }))
}
