import { formatMonthKey, formatMonthOverMonthLabel } from '@/lib/wonSalesSummary'
import type { WonSalesSummary } from '@/types/dealAnalytics'

function SummaryStat({
  label,
  value,
  hint,
  accent,
}: {
  label: string
  value: string
  hint?: string
  accent?: 'positive' | 'negative' | 'neutral'
}) {
  const accentClass =
    accent === 'positive'
      ? 'text-emerald-700'
      : accent === 'negative'
        ? 'text-red-600'
        : 'text-slate-900'

  return (
    <article className="rounded-lg border border-slate-100 bg-slate-50/80 px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${accentClass}`}>{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </article>
  )
}

export function WonSalesSummaryStrip({
  summary,
  historicalHint = 'Cierres ganados históricos de la marca',
}: {
  summary: WonSalesSummary
  historicalHint?: string
}) {
  const momLabel = formatMonthOverMonthLabel(summary)
  const momAccent =
    summary.month_over_month_change_pct == null
      ? undefined
      : summary.month_over_month_change_pct > 0
        ? 'positive'
        : summary.month_over_month_change_pct < 0
          ? 'negative'
          : 'neutral'

  return (
    <div className="mb-4 grid gap-3 sm:grid-cols-3">
      <SummaryStat
        label="Unidades vendidas (total)"
        value={summary.total_units.toLocaleString('es-CO')}
        hint={historicalHint}
      />
      <SummaryStat
        label={`Unidades este mes (${formatMonthKey(summary.this_month_key)})`}
        value={summary.units_this_month.toLocaleString('es-CO')}
        hint="Mes calendario en curso (fecha de cierre)"
      />
      <SummaryStat
        label="Comparativa mes anterior"
        value={
          summary.month_over_month_change_pct != null
            ? `${summary.month_over_month_change_pct > 0 ? '+' : ''}${summary.month_over_month_change_pct}%`
            : summary.units_this_month > 0
              ? '↑'
              : '—'
        }
        hint={momLabel}
        accent={momAccent}
      />
    </div>
  )
}
