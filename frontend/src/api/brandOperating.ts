import { apiGet } from './client'
import type { BrandOperatingData, DealAnalyticsEnvelope } from '@/types/dealAnalytics'

export function fetchBrandOperating(brand: string) {
  return apiGet<DealAnalyticsEnvelope<BrandOperatingData>>(
    `/api/v1/deal-analytics/brands/${encodeURIComponent(brand)}/operating`,
  )
}
