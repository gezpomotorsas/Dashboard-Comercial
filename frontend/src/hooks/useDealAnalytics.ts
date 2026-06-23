import { useQuery } from '@tanstack/react-query'
import {
  fetchActivityOutcomes,
  fetchBrandsZones,
  fetchDealAnalyticsFilters,
  fetchDealExplorer,
  fetchDealFunnel,
  fetchDealOwners,
  fetchDealsByBrand,
  fetchDealsByPipeline,
  fetchDealsByStage,
  fetchDealsByZone,
  fetchDealSummary,
  fetchInactivityDistribution,
} from '@/api/dealAnalytics'
import type { DealAnalyticsFilterValues } from '@/types/dealAnalytics'
import { cachedQueryDefaults } from '@/lib/queryDefaults'

export function useDealAnalyticsFilters() {
  return useQuery({
    queryKey: ['deal-analytics-filters'],
    queryFn: fetchDealAnalyticsFilters,
    ...cachedQueryDefaults,
  })
}

export function useDealSummary(filters: DealAnalyticsFilterValues, enabled = true) {
  return useQuery({
    queryKey: ['deal-analytics-summary', filters],
    queryFn: () => fetchDealSummary(filters),
    enabled,
    ...cachedQueryDefaults,
  })
}

export function useDealsByStage(filters: DealAnalyticsFilterValues, enabled = true) {
  return useQuery({
    queryKey: ['deal-analytics-by-stage', filters],
    queryFn: () => fetchDealsByStage(filters),
    enabled,
    ...cachedQueryDefaults,
  })
}

export function useDealsByPipeline(filters: DealAnalyticsFilterValues, enabled = true) {
  return useQuery({
    queryKey: ['deal-analytics-by-pipeline', filters],
    queryFn: () => fetchDealsByPipeline(filters),
    enabled,
    ...cachedQueryDefaults,
  })
}

export function useDealsByBrand(filters: DealAnalyticsFilterValues, enabled = true) {
  return useQuery({
    queryKey: ['deal-analytics-by-brand', filters],
    queryFn: () => fetchDealsByBrand(filters),
    enabled,
    ...cachedQueryDefaults,
  })
}

export function useDealsByZone(filters: DealAnalyticsFilterValues, enabled = true) {
  return useQuery({
    queryKey: ['deal-analytics-by-zone', filters],
    queryFn: () => fetchDealsByZone(filters),
    enabled,
    ...cachedQueryDefaults,
  })
}

export function useBrandsZones(filters: DealAnalyticsFilterValues, enabled = true) {
  return useQuery({
    queryKey: ['deal-analytics-brands-zones', filters],
    queryFn: () => fetchBrandsZones(filters),
    enabled,
    ...cachedQueryDefaults,
  })
}

export function useDealOwners(filters: DealAnalyticsFilterValues, enabled = true) {
  return useQuery({
    queryKey: ['deal-analytics-owners', filters],
    queryFn: () => fetchDealOwners(filters),
    enabled,
    ...cachedQueryDefaults,
  })
}

export function useDealExplorer(
  filters: DealAnalyticsFilterValues & { limit?: number; offset?: number },
  enabled = true,
) {
  return useQuery({
    queryKey: ['deal-analytics-explorer', filters],
    queryFn: () => fetchDealExplorer(filters),
    enabled,
    ...cachedQueryDefaults,
  })
}

export function useDealFunnel(filters: DealAnalyticsFilterValues, enabled = true) {
  return useQuery({
    queryKey: ['deal-analytics-funnel', filters],
    queryFn: () => fetchDealFunnel(filters),
    enabled,
    ...cachedQueryDefaults,
  })
}

export function useActivityOutcomes(filters: DealAnalyticsFilterValues, enabled = true) {
  return useQuery({
    queryKey: ['deal-analytics-activity-outcomes', filters],
    queryFn: () => fetchActivityOutcomes(filters),
    enabled,
    ...cachedQueryDefaults,
  })
}

export function useInactivityDistribution(filters: DealAnalyticsFilterValues, enabled = true) {
  return useQuery({
    queryKey: ['deal-analytics-inactivity', filters],
    queryFn: () => fetchInactivityDistribution(filters),
    enabled,
    ...cachedQueryDefaults,
  })
}
