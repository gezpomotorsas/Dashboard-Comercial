import { HelpCircle } from 'lucide-react'
import { MetricTooltipContent } from '@/components/ui/MetricTooltipContent'
import { cn } from '@/lib/utils'

export function MetricTableHeader({
  label,
  tooltip,
  className,
  as = 'th',
}: {
  label: string
  tooltip: string
  className?: string
  as?: 'th' | 'span'
}) {
  const content = (
    <span className="group relative inline-flex cursor-help items-start gap-1 text-left">
      <span className="border-b border-dotted border-slate-400 leading-snug">{label}</span>
      <HelpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden />
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute bottom-[calc(100%+6px)] left-1/2 z-50 hidden w-max max-w-[16rem]',
          '-translate-x-1/2 rounded-lg bg-slate-900 px-3 py-2.5 text-xs font-normal text-white shadow-xl',
          'group-hover:block group-focus-within:block',
        )}
      >
        <MetricTooltipContent text={tooltip} />
      </span>
    </span>
  )

  if (as === 'span') {
    return <span className={cn('font-medium', className)}>{content}</span>
  }

  return <th className={cn('px-2 py-2 font-medium', className)}>{content}</th>
}
