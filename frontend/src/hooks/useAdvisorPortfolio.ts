import { useQuery } from '@tanstack/react-query'
import { fetchAdvisorPortfolio } from '@/api/advisorPortfolio'
import type { OperatingBrand } from '@/hooks/useBrandOperating'
import { cachedQueryDefaults } from '@/lib/queryDefaults'

export function useAdvisorPortfolio(brand: OperatingBrand, ownerId: string | undefined) {
  return useQuery({
    queryKey: ['advisor-portfolio', brand, ownerId],
    queryFn: () => fetchAdvisorPortfolio(brand, ownerId!),
    enabled: Boolean(ownerId),
    ...cachedQueryDefaults,
  })
}
