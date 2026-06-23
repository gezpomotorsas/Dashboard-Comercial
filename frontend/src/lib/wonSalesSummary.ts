import type { WonSalesSummary } from '@/types/dealAnalytics'

export type MonthOverMonthDisplay = {
  primary: string
  secondary: string | null
  detail: string | null
  tone: 'up' | 'down' | 'flat' | 'new' | 'none'
  title: string
}

const monthFormatter = new Intl.DateTimeFormat('es-CO', { month: 'long', year: 'numeric' })

export function formatMonthKey(monthKey: string): string {
  const [year, month] = monthKey.split('-').map(Number)
  if (!year || !month) return monthKey
  return monthFormatter.format(new Date(year, month - 1, 1))
}

export function formatMonthOverMonthLabel(summary: WonSalesSummary): string {
  const thisLabel = formatMonthKey(summary.this_month_key)
  const prevLabel = formatMonthKey(summary.previous_month_key)
  const prevUnits = summary.units_previous_month

  if (summary.month_over_month_change_pct == null) {
    if (summary.units_this_month === 0) return `Sin registros en ${thisLabel}`
    return `${thisLabel} vs ${prevLabel}: al alza (mes anterior en 0, ahora ${summary.units_this_month})`
  }

  const sign = summary.month_over_month_change_pct > 0 ? '+' : ''
  return `${thisLabel} vs ${prevLabel}: ${sign}${summary.month_over_month_change_pct}% (${summary.units_this_month} vs ${prevUnits} u.)`
}

export function formatMonthComparisonLine(summary: WonSalesSummary): string {
  return `${formatMonthKey(summary.this_month_key)} vs ${formatMonthKey(summary.previous_month_key)}`
}

export function formatMonthOverMonthDisplay(summary: WonSalesSummary): MonthOverMonthDisplay {
  const title = formatMonthOverMonthLabel(summary)
  const monthLine = formatMonthComparisonLine(summary)
  const { units_this_month: current, units_previous_month: previous } = summary

  if (summary.month_over_month_change_pct == null) {
    if (current === 0) {
      return { primary: '—', secondary: monthLine, detail: 'Sin actividad este mes', tone: 'none', title }
    }
    return {
      primary: '↑ Nuevo',
      secondary: monthLine,
      detail: `${current} vs 0 unidades`,
      tone: 'new',
      title,
    }
  }

  const pct = summary.month_over_month_change_pct
  const sign = pct > 0 ? '+' : ''
  return {
    primary: `${sign}${pct}%`,
    secondary: monthLine,
    detail: `${current} vs ${previous} unidades`,
    tone: pct > 0 ? 'up' : pct < 0 ? 'down' : 'flat',
    title,
  }
}
