import { apiGet } from './client'
import type { AdvisorPortfolioData, DealAnalyticsEnvelope } from '@/types/dealAnalytics'

export function fetchAdvisorPortfolio(brand: string, ownerId: string) {
  return apiGet<DealAnalyticsEnvelope<AdvisorPortfolioData>>(
    `/api/v1/deal-analytics/brands/${encodeURIComponent(brand)}/advisors/${encodeURIComponent(ownerId)}/portfolio`,
  )
}
