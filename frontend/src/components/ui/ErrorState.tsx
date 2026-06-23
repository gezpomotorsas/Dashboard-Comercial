import { AlertCircle } from 'lucide-react'

interface ErrorStateProps {
  title?: string
  message: string
  onRetry?: () => void
}

export function ErrorState({
  title = 'No se pudo cargar el dashboard',
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-12 text-center">
      <AlertCircle className="h-10 w-10 text-rose-500" aria-hidden />
      <div>
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 max-w-lg text-sm text-slate-600">{message}</p>
      </div>
      {onRetry ? (
        <button type="button" className="btn-primary" onClick={onRetry}>
          Reintentar
        </button>
      ) : null}
    </div>
  )
}
