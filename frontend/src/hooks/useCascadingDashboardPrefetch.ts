import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { runCascadingPrefetch } from '@/lib/cascadingPrefetch'
import type { OperatingBrand } from '@/hooks/useBrandOperating'

let cascadePromise: Promise<void> | null = null

/**
 * Precarga en segundo plano: marcas → carteras de asesores → comparativa de grupos.
 * Una sola ejecución por sesión (hasta recargar la página).
 */
export function useCascadingDashboardPrefetch(activeBrand?: OperatingBrand) {
  const queryClient = useQueryClient()
  const startedRef = useRef(false)

  useEffect(() => {
    if (startedRef.current || cascadePromise) return
    startedRef.current = true
    cascadePromise = runCascadingPrefetch(queryClient, { activeBrand })
  }, [queryClient, activeBrand])
}
