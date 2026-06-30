import { useMutation, useQueryClient } from '@tanstack/react-query'

export type UpdateAllResult = {
  ok: boolean
  message: string
  hubspot: { objects: string; associations: string; analytics: string }
  github: {
    ok: boolean
    message: string
    restart_required: boolean
  }
  restart_required: boolean
}

async function postUpdateAll(): Promise<UpdateAllResult> {
  const res = await fetch('/api/v1/launcher/update/all', {
    method: 'POST',
    headers: { Accept: 'application/json' },
  })
  const body = (await res.json().catch(() => ({}))) as UpdateAllResult & { detail?: string }
  if (!res.ok) {
    throw new Error(body.detail || body.message || `Error ${res.status}`)
  }
  return body
}

export function useLauncherUpdateAll() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: postUpdateAll,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['launcher', 'status'] })
      void queryClient.invalidateQueries({ queryKey: ['brand-operating'] })
      void queryClient.invalidateQueries({ queryKey: ['deal-analytics'] })
    },
  })
}
