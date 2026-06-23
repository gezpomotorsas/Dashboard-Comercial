import type { ContactAdvisorFields, ContactMethodologyData } from '@/types/contactMetrics'
import type { GroupPerformanceMetrics } from '@/types/advisorGroups'

export type { ContactMethodologyData } from '@/types/contactMetrics'

export type DealStatus = 'open' | 'won' | 'lost' | 'unknown'

export interface DealAnalyticsPopulation {
  total_deals: number
  included_deals: number
  excluded_deals: number
}

export interface DealAnalyticsEnvelope<T = unknown> {
  filters: Record<string, unknown>
  population: DealAnalyticsPopulation
  data: T
  data_quality: {
    status: string
    notes: string[]
    activity_coverage: string | null
    task_coverage?: string | null
    stage_history_coverage: string | null
  }
  configuration: {
    metadata_snapshot_at?: string | null
    field_mapping_version?: number
    dimension_mapping_version?: number
  }
  generated_at: string
  timezone: string
}

export interface StatusDistributionItem {
  status: string
  label: string
  count: number
}

export interface DealSummaryData {
  total_deals: number
  open_deals: number
  won_deals: number
  lost_deals: number
  unknown_status_deals: number
  open_pipeline_amount: number
  won_amount: number
  lost_amount: number
  stale_deals: number
  stale_pipeline_amount: number
  unattended_open_deals: number
  deals_without_owner: number
  deals_with_overdue_tasks: number
  open_managed_30d: number
  open_managed_30d_rate: number | null
  open_effective_contact_30d: number
  open_effective_contact_30d_rate: number | null
  status_distribution: StatusDistributionItem[]
  average_deal_amount: number | null
  median_deal_amount: number | null
  activity_coverage_note?: string
}

export interface DealGroupRow {
  key: string
  label: string
  count: number
  open_count?: number
  won_count?: number
  lost_count?: number
  open_pipeline_amount: number
  won_amount: number
}

export interface BrandZoneRow {
  brand_value: string
  brand_label: string
  zone_value: string
  zone_label: string
  total_deals: number
  open_deals: number
  won_deals: number
  lost_deals: number
  open_pipeline_amount: number
  won_amount: number
  managed_30d: number
  managed_30d_rate: number | null
  effective_contact_30d: number
  effective_contact_30d_rate: number | null
  stale_deals: number
  unattended_open_deals: number
  deals_with_overdue_tasks: number
  close_rate: number | null
}

export interface BrandStageGroupRow {
  commercial_group: string
  commercial_group_label: string
  display_order: number
  open_deals: number
  stale_45d: number
  with_overdue_tasks: number
  stages_detail: Array<{ stage_label: string; count: number }>
}

export interface BrandAdvisorRow extends ContactAdvisorFields {
  owner_id: string | null
  owner_name: string | null
  brand_value: string
  assigned_deals: number
  open_deals: number
  new_deals_7d: number
  new_deals_30d: number
  stale_45d_open: number
  tasks_completed: number
  tasks_open: number
  tasks_overdue: number
  deals_with_overdue_tasks: number
  managed_30d: number
  managed_30d_rate: number | null
  tasks_overdue_rate: number | null
  won_sales?: WonSalesSummary
  leads_created?: WonSalesSummary
  performance?: GroupPerformanceMetrics
}

export interface WonSalesSummary {
  total_units: number
  units_this_month: number
  units_previous_month: number
  month_over_month_change_pct: number | null
  this_month_key: string
  previous_month_key: string
}

export interface BrandOperatingData {
  brand_value: string
  brand_label: string
  stale_threshold_days?: number
  totals: {
    all_deals: number
    open_deals: number
    won_deals: number
    lost_deals: number
    stale_45d_open: number
    new_deals_7d: number
    new_deals_30d: number
  }
  won_sales_summary?: WonSalesSummary
  stage_groups: BrandStageGroupRow[]
  advisors: BrandAdvisorRow[]
  weekly_created: Array<{ week_start: string; deals_created: number }>
  weekly_won: Array<{ week_start: string; deals_closed: number; total_amount: number }>
  weekly_lost: Array<{ week_start: string; deals_closed: number; total_amount: number }>
  weekly_calls?: Array<{ week_start: string; calls: number }>
  activity_coverage_note?: string
  contact_methodology?: {
    version?: string
    contact_window_days?: number
    brand_summary?: ContactMethodologyData | null
    focus?: string
  }
}

export interface AdvisorPortfolioTask {
  task_id: string
  subject: string
  status: string | null
  status_label: string
  priority: string | null
  due_at: string | null
  created_at?: string | null
  is_completed: boolean
  is_overdue: boolean
  is_past_due: boolean
  is_completed_late?: boolean
  days_unresolved: number | null
  deal_id: string | null
  deal_name: string | null
  deal_stage_label?: string | null
  deal_commercial_group_label?: string | null
  deal_status?: string | null
  contact_id?: string | null
  contact_name?: string | null
}

export interface AdvisorPortfolioDeal {
  deal_id: string
  deal_name: string | null
  status: DealStatus
  stage_label: string | null
  commercial_group_label: string | null
  amount: number | null
  age_days: number | null
  days_in_current_stage: number | null
  days_since_last_activity: number | null
  days_since_effective_contact: number | null
  is_open: boolean
  is_stale_45d: boolean
  is_stale: boolean
  is_unattended: boolean
  has_overdue_tasks: boolean
  has_recent_activity_30d: boolean
  overdue_task_count: number
  open_task_count: number
  alert_reason: string | null
  unattended_reason: string | null
  created_at: string | null
}

export interface AdvisorPortfolioData {
  advisor: {
    owner_id: string | null
    owner_name: string
    brand_value: string
    brand_label: string
  }
  summary: {
    assigned_deals: number
    open_deals: number
    won_deals: number
    lost_deals: number
    stale_45d_open: number
    unattended_open: number
    deals_with_overdue_tasks: number
    open_pipeline_amount: number
    managed_30d_rate: number | null
    call_coverage_rate?: number | null
    whatsapp_coverage_rate?: number | null
    combined_coverage_rate?: number | null
    overdue_contact_21d?: number
    channel_overdue_21d?: number
    channel_overdue_21d_label?: string
    discipline_operational_score?: number | null
    discipline_operational_status?: string
    legacy_discipline_contact_score?: number | null
    discipline_contact_score?: number | null
    commercial_effectiveness_score?: number | null
    effectiveness_commercial_score?: number | null
  }
  won_sales?: WonSalesSummary
  charts: {
    by_commercial_group: Array<{
      commercial_group: string
      commercial_group_label: string
      display_order: number
      open_deals: number
      stale_45d: number
    }>
    open_health: Array<{ label: string; count: number }>
    inactivity_distribution: Array<{ bucket: string; count: number }>
    by_stage: Array<{ stage_label: string; count: number; stale_45d: number }>
    weekly_created: Array<{ week_start: string; deals_created: number }>
    weekly_won: Array<{ week_start: string; deals_closed: number; total_amount: number }>
    weekly_lost: Array<{ week_start: string; deals_closed: number; total_amount: number }>
    weekly_overdue_tasks: Array<{ week_start: string; tasks_overdue: number }>
    weekly_calls?: Array<{ week_start: string; count: number }>
    weekly_whatsapp?: Array<{ week_start: string; count: number }>
    duration_ranges?: Array<{ range: string; count: number }>
    channel_mix?: Record<string, number>
    calls_by_weekday?: Array<{ weekday: string; count: number }>
    whatsapp_by_weekday?: Array<{ weekday: string; count: number }>
    calls_by_time_band?: Array<{
      time_band: string
      calls: number
      unique_deals: number
      total_minutes?: number
      connected_rate?: number | null
    }>
    whatsapp_by_time_band?: Array<{ time_band: string; messages: number; unique_deals: number }>
  }
  contact_methodology?: ContactMethodologyData | null
  deals: AdvisorPortfolioDeal[]
  tasks: AdvisorPortfolioTask[]
  task_counts?: {
    total: number
    pending: number
    overdue: number
    completed_late: number
    completed: number
    excluded_orphan?: number
    excluded_reassigned_lead?: number
    excluded_closed_deal?: number
  }
  activity_coverage_note?: string
}

export interface DealExplorerItem {
  deal_id: string
  deal_name: string | null
  pipeline_label: string | null
  stage_label: string | null
  brand_label: string | null
  zone_label: string | null
  model_label: string | null
  status: DealStatus
  owner_name: string | null
  amount: number | null
  age_days: number | null
  days_in_current_stage: number | null
  last_activity_at: string | null
  days_since_last_activity: number | null
  days_since_effective_contact: number | null
  activity_count: number
  effective_contact_count: number
  contact_count: number
  open_task_count?: number
  overdue_task_count?: number
  is_stale: boolean
  is_unattended?: boolean
  unattended_reason?: string | null
  alert_reason?: string | null
  data_completeness_score: number | null
}

export interface OwnerAnalyticsRow {
  owner_id: string | null
  owner_name: string | null
  assigned_deals: number
  open_deals: number
  won_deals: number
  lost_deals: number
  open_pipeline_amount: number
  won_amount: number
  managed_7d: number
  managed_30d: number
  managed_60d: number
  managed_7d_rate: number | null
  managed_30d_rate: number | null
  managed_60d_rate: number | null
  effective_contact_30d: number
  effective_contact_30d_rate: number | null
  overdue_tasks_deals: number
  unattended_open_deals: number
  stale_open_deals: number
  no_activity_30d_open: number
  no_future_task_open: number
  close_rate: number | null
  discipline_score: number | null
  effectiveness_score: number | null
  management_status: string
  sample_size: number
  minimum_population_met: boolean
}

export interface FilterOption {
  value: string
  label: string
}

export interface DealAnalyticsFilterOptions {
  pipelines: FilterOption[]
  stages: FilterOption[]
  owners: FilterOption[]
  brands: FilterOption[]
  zones: FilterOption[]
  models: FilterOption[]
  sources: FilterOption[]
  statuses: FilterOption[]
  age_buckets: FilterOption[]
  stage_age_buckets: FilterOption[]
  inactivity_buckets: FilterOption[]
}

export interface ActivityOutcomesData {
  deals_managed_last_7d?: number
  deals_managed_last_30d?: number
  deals_managed_last_60d?: number
  deals_without_activity?: number
  deals_without_effective_contact?: number
}

export interface InactivityDistributionData {
  deals_without_activity_7d?: number
  deals_without_activity_30d?: number
  deals_without_activity_60d?: number
  deals_without_any_activity?: number
  distribution?: Array<{ bucket: string; count: number }>
}

export interface DealAnalyticsFilterValues {
  pipeline_id?: string
  stage_id?: string
  owner_id?: string
  status?: string
  brand_value?: string
  zone_value?: string
  is_stale?: boolean
  is_unattended?: boolean
  has_overdue_tasks?: boolean
  sort_by?: string
  sort_dir?: string
  limit?: number
  offset?: number
}
