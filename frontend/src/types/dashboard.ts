export type DataStatus = 'available' | 'partial' | 'unavailable'
export type Direction = 'higher_is_better' | 'lower_is_better' | 'informational'

export interface DashboardFiltersApplied {
  week_start: string
  week_end: string
  brand: string
  owner_id: string | null
  pipeline_id: string | null
}

export interface DashboardKpiCard {
  code: string
  label: string
  value: number | null
  unit: string
  previous_value: number | null
  change_value: number | null
  change_percentage: number | null
  direction: Direction
  data_status: DataStatus
  status_reason?: string | null
  display_value?: string | null
}

export interface TrendPoint {
  week_start: string
  week_label: string
  leads_created?: number
  deals_created?: number
  pipeline_created_amount?: number
  won_amount?: number
}

export interface BrandResultRow {
  brand: string
  brand_label: string
  leads_created: number | null
  leads_data_status: DataStatus
  deals_created: number
  won_deals: number
}

export interface CloseRateChart {
  won_deals: number
  lost_deals: number
  close_rate: number | null
  data_status: DataStatus
}

export interface AdvisorActivityRow {
  owner_id: string
  owner_name: string
  calls: number
  communications: number
  completed_meetings: number
  tasks: number
  notes: number
  total_effective: number
}

export interface FirstResponseBrandRow {
  brand: string
  brand_label: string
  average_first_response_minutes: number | null
  median_first_response_minutes: number | null
  sample_size: number
  data_status: DataStatus
}

export interface Contacted24hBrandRow {
  brand: string
  brand_label: string
  contacted_within_24h_rate: number | null
  eligible_contacts: number
  contacted_count: number
  data_status: DataStatus
}

export interface DataQualityRuleRow {
  rule_code: string
  label: string
  severity: string
  count: number
}

export interface DashboardCharts {
  leads_and_deals_trend: TrendPoint[]
  brand_results: BrandResultRow[]
  pipeline_vs_won: TrendPoint[]
  close_rate: CloseRateChart
  advisor_activities: AdvisorActivityRow[]
  first_response_by_brand: FirstResponseBrandRow[]
  contacted_within_24h_by_brand: Contacted24hBrandRow[]
  data_quality: DataQualityRuleRow[]
}

export interface DashboardMetadata {
  generated_at: string
  timezone: string
  activity_window_days: number
  email_tracking_enabled: boolean
  email_data_required: boolean
  owner_scope_active?: boolean
  owner_scope_note?: string | null
  metadata_snapshot_at?: string | null
  metadata_version?: string | null
  field_mapping_version?: number
  dimension_mapping_version?: number
}

export interface DashboardWeeklyResponse {
  filters: DashboardFiltersApplied
  cards: DashboardKpiCard[]
  charts: DashboardCharts
  metadata: DashboardMetadata
}

export interface FilterOption {
  value: string
  label: string
}

export interface DashboardFiltersResponse {
  weeks: FilterOption[]
  brands: FilterOption[]
  owners: FilterOption[]
  pipelines: FilterOption[]
  metadata: Record<string, unknown>
}

export interface DashboardQueryParams {
  week_start?: string
  brand?: string
  owner_id?: string
  pipeline_id?: string
}
