import type { DashboardCharts } from '../../types/dashboard'
import { LeadsDealsTrendChart } from './LeadsDealsTrendChart'
import { BrandResultsChart } from './BrandResultsChart'
import { PipelineVsWonChart } from './PipelineVsWonChart'
import { CloseRateChart } from './CloseRateChart'
import { AdvisorActivitiesChart } from './AdvisorActivitiesChart'
import { FirstResponseChart } from './FirstResponseChart'
import { Contacted24hChart } from './Contacted24hChart'
import { DataQualityChart } from './DataQualityChart'

interface DashboardChartsGridProps {
  charts: DashboardCharts
  activityWindowDays?: number
  ownerFilterActive?: boolean
}

export function DashboardChartsGrid({
  charts,
  activityWindowDays = 60,
  ownerFilterActive = false,
}: DashboardChartsGridProps) {
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <LeadsDealsTrendChart data={charts.leads_and_deals_trend} />
      <BrandResultsChart data={charts.brand_results} />
      <PipelineVsWonChart data={charts.pipeline_vs_won} />
      <CloseRateChart data={charts.close_rate} />
      <AdvisorActivitiesChart
        data={charts.advisor_activities}
        activityWindowDays={activityWindowDays}
        ownerFilterActive={ownerFilterActive}
      />
      <FirstResponseChart data={charts.first_response_by_brand} />
      <Contacted24hChart data={charts.contacted_within_24h_by_brand} />
      <DataQualityChart data={charts.data_quality} />
    </div>
  )
}
