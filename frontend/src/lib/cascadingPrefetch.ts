import type { QueryClient } from '@tanstack/react-query'
import { compareAdvisorGroups, fetchAdvisorGroups } from '@/api/advisorGroups'
import { fetchAdvisorPortfolio } from '@/api/advisorPortfolio'
import { fetchBrandOperating } from '@/api/brandOperating'
import type { OperatingBrand } from '@/hooks/useBrandOperating'
import type { AdvisorGroup } from '@/types/advisorGroups'
import type { BrandOperatingData, DealAnalyticsEnvelope } from '@/types/dealAnalytics'
import { cachedQueryDefaults } from '@/lib/queryDefaults'

export const ALL_OPERATING_BRANDS: OperatingBrand[] = ['voyah', 'mhero', 'shacman']

export type PrefetchPhase = 'brands' | 'advisors' | 'groups' | 'done'

export type CascadingPrefetchOptions = {
  activeBrand?: OperatingBrand
  onPhaseChange?: (phase: PrefetchPhase) => void
}

function brandOrder(activeBrand?: OperatingBrand): OperatingBrand[] {
  if (!activeBrand) return [...ALL_OPERATING_BRANDS]
  return [activeBrand, ...ALL_OPERATING_BRANDS.filter((b) => b !== activeBrand)]
}

function advisorRouteId(ownerId: string | null | undefined): string {
  return ownerId ?? 'unassigned'
}

function normalizeBrand(value: string | null | undefined): string {
  return (value ?? '').trim().toLowerCase()
}

async function prefetchBrand(queryClient: QueryClient, brand: OperatingBrand): Promise<void> {
  await queryClient.prefetchQuery({
    queryKey: ['brand-operating', brand],
    queryFn: () => fetchBrandOperating(brand),
    ...cachedQueryDefaults,
  })
}

function getBrandEnvelope(
  queryClient: QueryClient,
  brand: OperatingBrand,
): DealAnalyticsEnvelope<BrandOperatingData> | undefined {
  return queryClient.getQueryData(['brand-operating', brand])
}

async function prefetchAdvisorPortfolios(
  queryClient: QueryClient,
  brand: OperatingBrand,
): Promise<void> {
  const envelope = getBrandEnvelope(queryClient, brand)
  const advisors = envelope?.data?.advisors ?? []

  for (const advisor of advisors) {
    const ownerId = advisorRouteId(advisor.owner_id)
    await queryClient.prefetchQuery({
      queryKey: ['advisor-portfolio', brand, ownerId],
      queryFn: () => fetchAdvisorPortfolio(brand, ownerId),
      ...cachedQueryDefaults,
    })
  }
}

function sortedGroupIds(groups: AdvisorGroup[]): string[] {
  return groups.map((g) => g.id).sort()
}

async function prefetchGroupsForBrand(
  queryClient: QueryClient,
  brand: OperatingBrand,
  groups: AdvisorGroup[],
): Promise<void> {
  const brandGroups = groups.filter((g) => normalizeBrand(g.brand_value) === brand)
  if (brandGroups.length === 0) return

  const groupIds = sortedGroupIds(brandGroups)
  await queryClient.prefetchQuery({
    queryKey: ['groups-compare', brand, groupIds],
    queryFn: () => compareAdvisorGroups(brand, groupIds),
    ...cachedQueryDefaults,
  })
}

/** Precarga en cascada: marcas → carteras de asesores → grupos. */
export async function runCascadingPrefetch(
  queryClient: QueryClient,
  options: CascadingPrefetchOptions = {},
): Promise<void> {
  const order = brandOrder(options.activeBrand)

  options.onPhaseChange?.('brands')
  for (const brand of order) {
    await prefetchBrand(queryClient, brand)
  }

  options.onPhaseChange?.('advisors')
  for (const brand of order) {
    await prefetchAdvisorPortfolios(queryClient, brand)
  }

  options.onPhaseChange?.('groups')
  await queryClient.prefetchQuery({
    queryKey: ['advisor-groups'],
    queryFn: fetchAdvisorGroups,
    ...cachedQueryDefaults,
  })

  const groups = queryClient.getQueryData<AdvisorGroup[]>(['advisor-groups']) ?? []
  for (const brand of ALL_OPERATING_BRANDS) {
    await prefetchGroupsForBrand(queryClient, brand, groups)
  }

  options.onPhaseChange?.('done')
}
