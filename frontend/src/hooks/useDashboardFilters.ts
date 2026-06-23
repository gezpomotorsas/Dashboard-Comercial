import { useQuery } from '@tanstack/react-query'
import { fetchDashboardFilters } from '../api/dashboard'

export const DASHBOARD_FILTERS_KEY = ['dashboard', 'filters'] as const

export function useDashboardFilters() {
  return useQuery({
    queryKey: DASHBOARD_FILTERS_KEY,
    queryFn: ({ signal }) => fetchDashboardFilters(signal),
    staleTime: 5 * 60 * 1000,
  })
}
