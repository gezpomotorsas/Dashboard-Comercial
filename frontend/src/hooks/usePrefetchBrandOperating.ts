import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { fetchBrandOperating } from '@/api/brandOperating'
import { cachedQueryDefaults } from '@/lib/queryDefaults'
import type { OperatingBrand } from '@/hooks/useBrandOperating'

const ALL_BRANDS: OperatingBrand[] = ['voyah', 'mhero', 'shacman']

/**
 * @deprecated Usar useCascadingDashboardPrefetch (incluye marcas, asesores y grupos).
 * Mantenido por compatibilidad: solo precarga otras marcas si la cascada aún no corrió.
 */
export function usePrefetchAllBrands(activeBrand?: OperatingBrand) {
  const queryClient = useQueryClient()
  const doneRef = useRef(false)

  useEffect(() => {
    if (doneRef.current) return
    doneRef.current = true

    for (const brand of ALL_BRANDS) {
      if (brand === activeBrand) continue
      void queryClient.prefetchQuery({
        queryKey: ['brand-operating', brand],
        queryFn: () => fetchBrandOperating(brand),
        ...cachedQueryDefaults,
      })
    }
  }, [queryClient, activeBrand])
}
