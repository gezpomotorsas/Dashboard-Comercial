export function formatCopAbbrev(amount: number | null | undefined): string {
  if (amount == null) return 'Sin datos'
  const abs = Math.abs(amount)
  if (abs >= 1_000_000_000) {
    return `$${(amount / 1_000_000_000).toLocaleString('es-CO', { maximumFractionDigits: 1 })} MM`
  }
  if (abs >= 1_000_000) {
    return `$${(amount / 1_000_000).toLocaleString('es-CO', { maximumFractionDigits: 1 })} M`
  }
  if (abs >= 1_000) {
    return `$${Math.round(amount / 1_000).toLocaleString('es-CO')} mil`
  }
  return `$${amount.toLocaleString('es-CO')}`
}

export const formatCop = formatCopAbbrev

export function formatCopFull(amount: number): string {
  return `$ ${amount.toLocaleString('es-CO')} COP`
}

export function formatDurationMinutes(minutes: number | null | undefined): string {
  if (minutes == null) return 'Sin datos'
  if (minutes < 60) return `${Math.round(minutes)} min`
  const hours = minutes / 60
  if (hours < 24) return `${hours.toLocaleString('es-CO', { maximumFractionDigits: 1 })} h`
  return `${(hours / 24).toLocaleString('es-CO', { maximumFractionDigits: 1 })} d`
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) return 'Sin datos'
  return `${value}%`
}

export function formatCount(value: number | null | undefined): string {
  if (value == null) return 'Sin datos'
  return value.toLocaleString('es-CO')
}

export type TrendSentiment = 'positive' | 'negative' | 'neutral'

export function getTrendSentiment(
  change: number | null | undefined,
  direction: 'higher_is_better' | 'lower_is_better' | 'informational',
): TrendSentiment {
  if (change == null || change === 0 || direction === 'informational') return 'neutral'
  const improved = direction === 'higher_is_better' ? change > 0 : change < 0
  return improved ? 'positive' : 'negative'
}

export function getTrendArrow(change: number | null | undefined): 'up' | 'down' | 'flat' {
  if (change == null || change === 0) return 'flat'
  return change > 0 ? 'up' : 'down'
}

export function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}
