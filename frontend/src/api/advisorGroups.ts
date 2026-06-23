import { apiGet, apiPost, apiPatch, apiDelete } from './client'
import type {
  AdvisorGroup,
  GroupsCompareData,
  HubSpotListOption,
  HubSpotTeamOption,
} from '@/types/advisorGroups'
import type { DealAnalyticsEnvelope } from '@/types/dealAnalytics'

export function fetchAdvisorGroups() {
  return apiGet<AdvisorGroup[]>('/api/v1/advisor-groups')
}

export function fetchAdvisorGroup(groupId: string) {
  return apiGet<AdvisorGroup>(`/api/v1/advisor-groups/${encodeURIComponent(groupId)}`)
}

export function createAdvisorGroup(body: {
  name: string
  description?: string | null
  brand_value?: string | null
  members: Array<{ owner_id: string; owner_name?: string | null }>
}) {
  return apiPost<AdvisorGroup>('/api/v1/advisor-groups', body)
}

export function updateAdvisorGroup(
  groupId: string,
  body: {
    name?: string
    description?: string | null
    brand_value?: string | null
    members?: Array<{ owner_id: string; owner_name?: string | null }>
  },
) {
  return apiPatch<AdvisorGroup>(`/api/v1/advisor-groups/${encodeURIComponent(groupId)}`, body)
}

export function deleteAdvisorGroup(groupId: string) {
  return apiDelete<{ deleted: boolean }>(`/api/v1/advisor-groups/${encodeURIComponent(groupId)}`)
}

export function fetchHubSpotTeams() {
  return apiGet<HubSpotTeamOption[]>('/api/v1/advisor-groups/hubspot/teams')
}

export function fetchHubSpotLists() {
  return apiGet<HubSpotListOption[]>('/api/v1/advisor-groups/hubspot/lists')
}

export function importHubSpotTeam(teamId: string, brand?: string) {
  const params = new URLSearchParams({ team_id: teamId })
  if (brand) params.set('brand_value', brand)
  return apiPost<AdvisorGroup>(`/api/v1/advisor-groups/import/hubspot-team?${params}`)
}

export function importHubSpotList(listId: string, brand?: string) {
  const params = new URLSearchParams({ list_id: listId })
  if (brand) params.set('brand_value', brand)
  return apiPost<AdvisorGroup>(`/api/v1/advisor-groups/import/hubspot-list?${params}`)
}

export function compareAdvisorGroups(brand: string, groupIds: string[]) {
  return apiPost<DealAnalyticsEnvelope<GroupsCompareData>>('/api/v1/advisor-groups/compare', {
    brand_value: brand,
    group_ids: groupIds,
  })
}
