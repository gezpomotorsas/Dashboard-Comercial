export const STALE_DAYS_BY_BRAND: Record<string, number> = {
  voyah: 21,
  mhero: 21,
  shacman: 45,
}

export function staleThresholdDays(brand: string | undefined | null, fallback?: number): number {
  if (fallback != null) return fallback
  if (!brand) return 45
  return STALE_DAYS_BY_BRAND[brand.toLowerCase()] ?? 45
}

export function staleMetricShortLabel(brand: string, fallbackDays?: number): string {
  return `Estanc. ${staleThresholdDays(brand, fallbackDays)}d`
}

export function staleMetricLongLabel(brand: string, fallbackDays?: number): string {
  const days = staleThresholdDays(brand, fallbackDays)
  return `Estancados +${days}d sin actividad`
}

export function staleChartSeriesLabel(brand: string, fallbackDays?: number): string {
  return `Estancados ${staleThresholdDays(brand, fallbackDays)}d`
}

export function staleMetricTooltip(brand: string, fallbackDays?: number): string {
  const days = staleThresholdDays(brand, fallbackDays)
  return `Negocios abiertos sin ninguna actividad sincronizada en ${days}+ días, o sin actividad registrada en la ventana de sync.`
}
