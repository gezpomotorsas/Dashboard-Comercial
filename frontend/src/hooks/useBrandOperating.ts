import { useQuery } from '@tanstack/react-query'
import { fetchBrandOperating } from '@/api/brandOperating'
import { cachedQueryDefaults } from '@/lib/queryDefaults'

export type OperatingBrand = 'voyah' | 'mhero' | 'shacman'

export function useBrandOperating(brand: OperatingBrand) {
  return useQuery({
    queryKey: ['brand-operating', brand],
    queryFn: () => fetchBrandOperating(brand),
    ...cachedQueryDefaults,
  })
}
