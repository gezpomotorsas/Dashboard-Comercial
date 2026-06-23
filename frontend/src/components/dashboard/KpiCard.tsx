import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import type { DashboardKpiCard } from '@/types/dashboard'
import { Card, CardContent } from '@/components/ui/card'
import { DataStatusBadge } from '@/components/dashboard/DataStatusBadge'
import {
  formatCopAbbrev,
  formatCopFull,
  formatCount,
  formatDurationMinutes,
  formatPercent,
  getTrendSentiment,
} from '@/lib/format'
import { cn } from '@/lib/utils'

function displayValue(card: DashboardKpiCard): string {
  if (card.data_status === 'unavailable') return 'Sin datos'
  if (card.display_value) return card.display_value
  if (card.value == null) return 'Sin datos'

  switch (card.unit) {
    case 'cop':
      return formatCopAbbrev(card.value)
    case 'percent':
      return formatPercent(card.value)
    case 'minutes':
      return formatDurationMinutes(card.value)
    default:
      return formatCount(card.value)
  }
}

function tooltipValue(card: DashboardKpiCard): string | undefined {
  if (card.unit === 'cop' && card.value != null && card.data_status !== 'unavailable') {
    return formatCopFull(card.value)
  }
  return card.status_reason ?? undefined
}

export function KpiCard({ card }: { card: DashboardKpiCard }) {
  const sentiment = getTrendSentiment(card.change_value, card.direction)
  const TrendIcon =
    sentiment === 'positive' ? ArrowUpRight : sentiment === 'negative' ? ArrowDownRight : Minus

  const trendColor =
    sentiment === 'positive'
      ? 'text-green-600'
      : sentiment === 'negative'
        ? 'text-red-600'
        : 'text-slate-400'

  const changeLabel =
    card.change_percentage != null
      ? `${card.change_percentage > 0 ? '+' : ''}${card.change_percentage}%`
      : card.change_value != null
        ? `${card.change_value > 0 ? '+' : ''}${card.change_value}`
        : '—'

  return (
    <Card className="min-w-[220px] flex-1">
      <CardContent className="pt-5">
        <div className="mb-2 flex items-start justify-between gap-2">
          <p className="text-sm font-medium text-slate-600">{card.label}</p>
          <DataStatusBadge status={card.data_status} reason={card.status_reason} />
        </div>
        <p
          className="text-3xl font-bold tracking-tight text-slate-900"
          title={tooltipValue(card)}
        >
          {displayValue(card)}
        </p>
        <div className={cn('mt-3 flex items-center gap-1 text-sm font-medium', trendColor)}>
          <TrendIcon className="h-4 w-4" />
          <span>{changeLabel}</span>
          <span className="font-normal text-slate-400">vs. sem. anterior</span>
        </div>
      </CardContent>
    </Card>
  )
}
