import { Inbox } from 'lucide-react'

interface EmptyStateProps {
  title?: string
  message: string
}

export function EmptyState({
  title = 'Sin resultados',
  message,
}: EmptyStateProps) {
  return (
    <div className="flex h-56 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-200 bg-slate-50/80 text-center">
      <Inbox className="h-8 w-8 text-slate-400" aria-hidden />
      <p className="text-sm font-medium text-slate-700">{title}</p>
      <p className="max-w-sm text-sm text-slate-500">{message}</p>
    </div>
  )
}
