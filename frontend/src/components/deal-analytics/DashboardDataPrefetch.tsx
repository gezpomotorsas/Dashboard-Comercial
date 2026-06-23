import { useCascadingDashboardPrefetch } from '@/hooks/useCascadingDashboardPrefetch'

/** Inicia la precarga en cascada al abrir la aplicación. */
export function DashboardDataPrefetch() {
  useCascadingDashboardPrefetch()
  return null
}
