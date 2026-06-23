import { apiFetch } from './client'
import type {
  DashboardFiltersResponse,
  DashboardQueryParams,
  DashboardWeeklyResponse,
} from '@/types/dashboard'

function buildQuery(params: DashboardQueryParams): string {
  const search = new URLSearchParams()
  if (params.week_start) search.set('week_start', params.week_start)
  if (params.brand && params.brand !== 'all') search.set('brand', params.brand)
  if (params.owner_id && params.owner_id !== 'all') search.set('owner_id', params.owner_id)
  if (params.pipeline_id && params.pipeline_id !== 'all') {
    search.set('pipeline_id', params.pipeline_id)
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export function fetchWeeklyDashboard(
  params: DashboardQueryParams,
  signal?: AbortSignal,
): Promise<DashboardWeeklyResponse> {
  return apiFetch(`/api/v1/dashboard/weekly${buildQuery(params)}`, { signal })
}

export function fetchDashboardFilters(signal?: AbortSignal): Promise<DashboardFiltersResponse> {
  return apiFetch('/api/v1/dashboard/filters', { signal })
}
