import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { BrandOperatingPage } from '@/components/deal-analytics/BrandOperatingPage'
import { AdvisorPortfolioPage } from '@/components/deal-analytics/AdvisorPortfolioPage'
import { GrupoPage } from '@/components/deal-analytics/GrupoPage'
import { DealAnalyticsPage } from '@/components/deal-analytics/DealAnalyticsPage'
import { DashboardPage } from '@/components/dashboard/DashboardPage'
import { DashboardDataPrefetch } from '@/components/deal-analytics/DashboardDataPrefetch'
import { cachedQueryDefaults } from '@/lib/queryDefaults'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: cachedQueryDefaults,
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <DashboardDataPrefetch />
        <Routes>
          <Route path="/" element={<BrandOperatingPage />} />
          <Route path="/asesor" element={<AdvisorPortfolioPage />} />
          <Route path="/asesor/:brand" element={<AdvisorPortfolioPage />} />
          <Route path="/asesor/:brand/:ownerId" element={<AdvisorPortfolioPage />} />
          <Route path="/grupo" element={<GrupoPage />} />
          <Route path="/grupo/:groupId" element={<GrupoPage />} />
          <Route path="/analytics" element={<DealAnalyticsPage />} />
          <Route path="/legacy-weekly" element={<DashboardPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
