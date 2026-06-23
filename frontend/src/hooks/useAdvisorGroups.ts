import { useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  compareAdvisorGroups,
  createAdvisorGroup,
  deleteAdvisorGroup,
  fetchAdvisorGroups,
  fetchHubSpotLists,
  fetchHubSpotTeams,
  importHubSpotList,
  importHubSpotTeam,
  updateAdvisorGroup,
} from '@/api/advisorGroups'
import type { OperatingBrand } from '@/hooks/useBrandOperating'
import { cachedQueryDefaults } from '@/lib/queryDefaults'

export function useAdvisorGroups() {
  return useQuery({
    queryKey: ['advisor-groups'],
    queryFn: fetchAdvisorGroups,
    ...cachedQueryDefaults,
  })
}

export function useHubSpotTeams() {
  return useQuery({
    queryKey: ['hubspot-teams'],
    queryFn: fetchHubSpotTeams,
    ...cachedQueryDefaults,
  })
}

export function useHubSpotLists() {
  return useQuery({
    queryKey: ['hubspot-lists'],
    queryFn: fetchHubSpotLists,
    ...cachedQueryDefaults,
  })
}

export function useGroupsCompare(brand: OperatingBrand, groupIds: string[]) {
  const sortedIds = useMemo(() => [...groupIds].sort(), [groupIds])
  return useQuery({
    queryKey: ['groups-compare', brand, sortedIds],
    queryFn: () => compareAdvisorGroups(brand, sortedIds),
    enabled: sortedIds.length > 0,
    ...cachedQueryDefaults,
  })
}

export function useAdvisorGroupMutations() {
  const queryClient = useQueryClient()
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['advisor-groups'] })
    void queryClient.invalidateQueries({ queryKey: ['groups-compare'] })
  }

  return {
    create: useMutation({
      mutationFn: createAdvisorGroup,
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({ id, body }: { id: string; body: Parameters<typeof updateAdvisorGroup>[1] }) =>
        updateAdvisorGroup(id, body),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: deleteAdvisorGroup,
      onSuccess: invalidate,
    }),
    importTeam: useMutation({
      mutationFn: ({ teamId, brand }: { teamId: string; brand?: string }) =>
        importHubSpotTeam(teamId, brand),
      onSuccess: invalidate,
    }),
    importList: useMutation({
      mutationFn: ({ listId, brand }: { listId: string; brand?: string }) =>
        importHubSpotList(listId, brand),
      onSuccess: invalidate,
    }),
  }
}
