import { apiGet } from './client'
import type {
  DealAnalyticsEnvelope,
  DealAnalyticsFilterOptions,
  DealAnalyticsFilterValues,
  DealExplorerItem,
  DealGroupRow,
  DealSummaryData,
  OwnerAnalyticsRow,
} from '@/types/dealAnalytics'

function toParams(filters: DealAnalyticsFilterValues = {}): string {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '' && value !== 'all') {
      params.set(key, String(value))
    }
  })
  const query = params.toString()
  return query ? `?${query}` : ''
}

export function fetchDealAnalyticsFilters() {
  return apiGet<DealAnalyticsFilterOptions>('/api/v1/deal-analytics/filters')
}

export function fetchDealSummary(filters?: DealAnalyticsFilterValues) {
  return apiGet<DealAnalyticsEnvelope<DealSummaryData>>(
    `/api/v1/deal-analytics/summary${toParams(filters)}`,
  )
}

export function fetchDealsByStage(filters?: DealAnalyticsFilterValues) {
  return apiGet<DealAnalyticsEnvelope<DealGroupRow[]>>(
    `/api/v1/deal-analytics/by-stage${toParams(filters)}`,
  )
}

export function fetchDealsByPipeline(filters?: DealAnalyticsFilterValues) {
  return apiGet<DealAnalyticsEnvelope<DealGroupRow[]>>(
    `/api/v1/deal-analytics/by-pipeline${toParams(filters)}`,
  )
}

export function fetchDealsByBrand(filters?: DealAnalyticsFilterValues) {
  return apiGet<DealAnalyticsEnvelope<DealGroupRow[]>>(
    `/api/v1/deal-analytics/by-brand${toParams(filters)}`,
  )
}

export function fetchDealsByZone(filters?: DealAnalyticsFilterValues) {
  return apiGet<DealAnalyticsEnvelope<DealGroupRow[]>>(
    `/api/v1/deal-analytics/by-zone${toParams(filters)}`,
  )
}

export function fetchBrandsZones(filters?: DealAnalyticsFilterValues) {
  return apiGet<DealAnalyticsEnvelope<import('@/types/dealAnalytics').BrandZoneRow[]>>(
    `/api/v1/deal-analytics/brands-zones${toParams(filters)}`,
  )
}

export function fetchDealOwners(filters?: DealAnalyticsFilterValues) {
  return apiGet<DealAnalyticsEnvelope<OwnerAnalyticsRow[]>>(
    `/api/v1/deal-analytics/owners${toParams(filters)}`,
  )
}

export function fetchDealExplorer(filters?: DealAnalyticsFilterValues & { limit?: number; offset?: number }) {
  const params = toParams(filters)
  return apiGet<DealAnalyticsEnvelope<{ items: DealExplorerItem[]; total: number }>>(
    `/api/v1/deal-analytics/deals${params}`,
  )
}

export function fetchDealFunnel(filters?: DealAnalyticsFilterValues) {
  return apiGet<DealAnalyticsEnvelope<unknown[]>>(
    `/api/v1/deal-analytics/funnel${toParams(filters)}`,
  )
}

export function fetchActivityOutcomes(filters?: DealAnalyticsFilterValues) {
  return apiGet<DealAnalyticsEnvelope<unknown>>(
    `/api/v1/deal-analytics/activity-outcomes${toParams(filters)}`,
  )
}

export function fetchInactivityDistribution(filters?: DealAnalyticsFilterValues) {
  return apiGet<DealAnalyticsEnvelope<unknown>>(
    `/api/v1/deal-analytics/inactivity-distribution${toParams(filters)}`,
  )
}
