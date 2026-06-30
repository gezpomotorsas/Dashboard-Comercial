import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { useLauncherStatus } from '@/hooks/useLauncherStatus'
import { useLauncherUpdateAll } from '@/hooks/useLauncherUpdateAll'

function formatBuiltAt(iso: string | null | undefined): string {
  if (!iso) return 'Sin registro'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return 'Sin registro'
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/Bogota',
  }).format(date)
}

/** Barra inferior: última actualización app + botón HubSpot + GitHub. */
export function LauncherUpdateBar() {
  const { data, isLoading } = useLauncherStatus()
  const updateAll = useLauncherUpdateAll()
  const [feedback, setFeedback] = useState<string | null>(null)

  if (!import.meta.env.PROD) return null

  const builtAtLabel = formatBuiltAt(data?.built_at)
  const commitLabel =
    data?.local_commit && data.local_commit !== 'local' ? data.local_commit.slice(0, 7) : null
  const hasAppUpdate = Boolean(data?.update_available)
  const busy = updateAll.isPending

  async function handleUpdate() {
    setFeedback(null)
    try {
      const result = await updateAll.mutateAsync()
      setFeedback(
        result.ok
          ? `${result.message} Datos de Supabase actualizados.`
          : `${result.message}`,
      )
      if (result.restart_required) {
        const restart = window.confirm(
          'Hay una nueva versión de la app. ¿Reiniciar ahora para aplicarla?',
        )
        if (restart) {
          await fetch('/api/v1/launcher/restart', { method: 'POST' })
        }
      }
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'No se pudo actualizar')
    }
  }

  return (
    <footer
      className="fixed inset-x-0 bottom-0 z-[100] border-t border-slate-200 bg-white/95 px-4 py-2 shadow-[0_-4px_16px_rgba(15,23,42,0.06)] backdrop-blur-sm"
      role="contentinfo"
    >
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
        <div className="min-w-0 flex-1">
          <span className="font-medium text-slate-800">Última actualización app: </span>
          {isLoading ? (
            <span>Cargando…</span>
          ) : (
            <span>
              {builtAtLabel}
              {commitLabel ? ` · ${commitLabel}` : ''}
              {data?.app_version ? ` · v${data.app_version}` : ''}
            </span>
          )}
          {hasAppUpdate ? (
            <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              Nueva versión en GitHub
            </span>
          ) : null}
          {feedback ? (
            <p className="mt-1 text-xs text-slate-500" role="status">
              {feedback}
            </p>
          ) : null}
        </div>

        <button
          type="button"
          onClick={() => void handleUpdate()}
          disabled={busy}
          className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-teal-700 bg-teal-700 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-teal-800 disabled:opacity-60"
          title="Sincroniza HubSpot → Supabase, recalcula métricas y comprueba GitHub"
        >
          <RefreshCw className={`h-4 w-4 ${busy ? 'animate-spin' : ''}`} aria-hidden />
          {busy ? 'Actualizando Supabase…' : 'Actualizar Supabase y app'}
        </button>
      </div>
    </footer>
  )
}
