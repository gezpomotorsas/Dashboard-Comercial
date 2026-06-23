/** Opciones compartidas de React Query para evitar recargas al cambiar pestañas/vistas. */
export const QUERY_STALE_MS = 5 * 60_000
export const QUERY_GC_MS = 30 * 60_000

export const cachedQueryDefaults = {
  staleTime: QUERY_STALE_MS,
  gcTime: QUERY_GC_MS,
  retry: 1,
  refetchOnMount: false,
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
} as const
