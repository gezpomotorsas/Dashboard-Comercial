import { cn } from '@/lib/utils'
import { formatMonthOverMonthDisplay } from '@/lib/wonSalesSummary'
import type { WonSalesSummary } from '@/types/dealAnalytics'

const toneClass = {
  up: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  down: 'border-red-200 bg-red-50 text-red-700',
  flat: 'border-slate-200 bg-slate-50 text-slate-600',
  new: 'border-sky-200 bg-sky-50 text-sky-800',
  none: 'border-slate-200 bg-slate-50 text-slate-400',
} as const

export function MonthOverMonthBadge({ summary }: { summary: WonSalesSummary }) {
  const display = formatMonthOverMonthDisplay(summary)

  return (
    <span
      className={cn(
        'inline-flex min-w-[7.5rem] max-w-[11rem] flex-col items-center gap-1 rounded-lg border px-2.5 py-2 text-center',
        toneClass[display.tone],
      )}
      title={display.title}
    >
      <span className="text-sm font-semibold leading-none">{display.primary}</span>
      {display.secondary ? (
        <span className="text-[10px] font-medium leading-snug">{display.secondary}</span>
      ) : null}
      {display.detail ? (
        <span className="text-[10px] leading-tight opacity-75">{display.detail}</span>
      ) : null}
    </span>
  )
}
