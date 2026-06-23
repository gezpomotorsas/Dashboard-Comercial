import type { WonSalesSummary } from '@/types/dealAnalytics'

export type GroupSource = 'manual' | 'hubspot_team' | 'hubspot_list'

export interface AdvisorGroupMember {
  owner_id: string
  owner_name: string | null
}

export interface AdvisorGroup {
  id: string
  name: string
  description: string | null
  brand_value: string | null
  source: GroupSource
  hubspot_source_id: string | null
  hubspot_source_label: string | null
  members: AdvisorGroupMember[]
  member_count: number
  created_at: string | null
  updated_at: string | null
}

export interface HubSpotTeamOption {
  team_id: string
  team_name: string
  member_count: number
  owner_ids: string[]
}

export interface HubSpotListOption {
  list_id: string
  name: string
  object_type_id: string | null
  processing_type: string | null
  size: number | null
}

import type { ContactAdvisorFields, ContactMethodologyData } from '@/types/contactMetrics'

export interface GroupCompareAdvisorRow extends ContactAdvisorFields {
  owner_id: string | null
  owner_name: string
  open_deals: number
  new_deals_7d: number
  new_deals_30d: number
  stale_45d_open: number
  managed_30d_rate: number | null
  tasks_overdue: number
}

export interface GroupPerformanceMetrics {
  won_sales: WonSalesSummary
  leads_created: WonSalesSummary
  tasks_overdue: number
  tasks_overdue_monthly: WonSalesSummary
  tasks_completed_monthly: WonSalesSummary
  tasks_managed_monthly: WonSalesSummary
  calls_monthly: WonSalesSummary
  whatsapp_monthly: WonSalesSummary
}

export interface GroupCompareRow {
  group_id: string
  group_name: string
  source?: GroupSource
  hubspot_source_label?: string | null
  member_count: number
  assigned_deals: number
  open_deals: number
  new_deals_7d: number
  new_deals_30d: number
  stale_45d_open: number
  tasks_completed: number
  tasks_open: number
  tasks_overdue: number
  deals_with_overdue_tasks: number
  managed_30d_rate: number | null
  contact_methodology?: ContactMethodologyData | null
  performance?: GroupPerformanceMetrics
  advisors: GroupCompareAdvisorRow[]
}

export interface GroupsCompareData {
  brand_value: string
  brand_label: string
  groups: GroupCompareRow[]
}
