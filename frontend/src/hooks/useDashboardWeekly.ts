import { useQuery } from '@tanstack/react-query'
import { fetchWeeklyDashboard } from '../api/dashboard'
import type { DashboardQueryParams } from '../types/dashboard'

export const DASHBOARD_WEEKLY_KEY = 'dashboard-weekly'

export function useDashboardWeekly(params: DashboardQueryParams | null) {
  return useQuery({
    queryKey: [DASHBOARD_WEEKLY_KEY, params],
    queryFn: ({ signal }) => fetchWeeklyDashboard(params!, signal),
    enabled: Boolean(params?.week_start),
    staleTime: 60 * 1000,
  })
}
