/** Tipos compartidos para métricas de contacto (Etapa 2). */

export interface ContactMetricsCalls {
  total_calls: number
  outbound_calls?: number
  inbound_calls?: number
  connected_calls?: number
  unanswered_calls?: number
  unique_deals_called: number
  call_coverage_rate: number | null
  call_coverage_rate_7d?: number | null
  call_coverage_rate_15d?: number | null
  call_coverage_rate_30d?: number | null
  call_coverage_numerator?: number
  call_coverage_denominator?: number
  deals_without_calls?: number
  deals_called_last_7d?: number
  deals_called_last_15d?: number
  deals_called_last_21d?: number
  deals_called_last_30d?: number
  total_call_minutes?: number | null
  average_call_duration_seconds?: number | null
  median_call_duration_seconds?: number | null
  percentile_75?: number | null
  percentile_90?: number | null
  duration_data_status?: string
  duration_coverage_percentage?: number | null
  duration_ranges?: Array<{ range: string; count: number }>
  weekly_trend?: Array<{ week_start: string; count: number }>
  by_weekday?: Array<{ weekday: string; count: number }>
  by_time_band?: Array<{
    time_band: string
    calls: number
    unique_deals: number
    total_minutes?: number
    connected_rate?: number | null
  }>
  duration_note?: string | null
}

export interface ContactMetricsWhatsapp {
  whatsapp_messages: number
  unique_deals_with_whatsapp: number
  whatsapp_coverage_rate: number | null
  whatsapp_coverage_numerator?: number
  whatsapp_coverage_denominator?: number
  estimated_whatsapp_sessions?: number
  average_messages_per_session?: number | null
  median_messages_per_session?: number | null
  messages_per_deal_average?: number | null
  messages_per_deal_median?: number | null
  deals_with_whatsapp_7d?: number
  deals_with_whatsapp_21d?: number
  deals_with_whatsapp_30d?: number
  session_estimation_warning?: string
  weekly_trend?: Array<{ week_start: string; count: number }>
  by_weekday?: Array<{ weekday: string; count: number }>
  by_time_band?: Array<{ time_band: string; messages: number; unique_deals: number }>
}

export interface ContactMetricsCoverage {
  combined_contact_coverage_rate: number | null
  combined_contact_coverage_numerator?: number
  combined_contact_coverage_denominator?: number
  deals_no_recent_contact?: number
  deals_call_only?: number
  deals_whatsapp_only?: number
  deals_multichannel?: number
  overdue_contact_21d?: number
  overdue_contact_21d_rate?: number | null
  channel_overdue_21d?: number
  channel_overdue_21d_rate?: number | null
  channel_overdue_21d_label?: string
  channel_mix?: Record<string, number>
}

export interface ContactMetricsEvaluation {
  discipline_operational_score?: number | null
  discipline_operational_status?: string
  legacy_discipline_contact_score?: number | null
  discipline_contact_score?: number | null
  commercial_effectiveness_score?: number | null
  commercial_effectiveness_status?: string
  effectiveness_commercial_score?: number | null
  load_alert_40_plus?: boolean
  load_classification?: string
}

export interface ContactMethodologyData {
  contact_window_days?: number
  active_deals?: number
  assigned_deals?: number
  won_deals?: number
  close_rate?: number | null
  calls?: ContactMetricsCalls
  whatsapp?: ContactMetricsWhatsapp
  coverage?: ContactMetricsCoverage
  evaluation?: ContactMetricsEvaluation
  data_quality?: Record<string, string>
}

export interface ContactAdvisorFields {
  call_coverage_rate?: number | null
  call_coverage_rate_7d?: number | null
  call_coverage_rate_15d?: number | null
  call_coverage_rate_30d?: number | null
  whatsapp_coverage_rate?: number | null
  combined_coverage_rate?: number | null
  overdue_contact_21d?: number
  overdue_contact_21d_rate?: number | null
  channel_overdue_21d?: number
  channel_overdue_21d_rate?: number | null
  total_calls?: number
  unique_deals_called?: number
  total_call_minutes?: number | null
  median_call_duration_seconds?: number | null
  duration_data_status?: string
  whatsapp_messages?: number
  unique_deals_with_whatsapp?: number
  estimated_whatsapp_sessions?: number
  discipline_operational_score?: number | null
  discipline_operational_status?: string | null
  legacy_discipline_contact_score?: number | null
  discipline_contact_score?: number | null
  commercial_effectiveness_score?: number | null
  effectiveness_commercial_score?: number | null
  load_classification?: string
  close_rate?: number | null
  contact_metrics?: ContactMethodologyData
}
