import { useQuery } from '@tanstack/react-query'

export type LauncherUpdateStatus = {
  local_commit: string
  remote_commit: string
  update_available: boolean
  source: string
  release_tag: string | null
  release_name: string | null
  message: string
  app_version: string
  built_at: string | null
  repo: string | null
}

async function fetchLauncherStatus(): Promise<LauncherUpdateStatus | null> {
  const res = await fetch('/api/v1/launcher/update/status', {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) return null
  const contentType = res.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) return null
  return res.json() as Promise<LauncherUpdateStatus>
}

export function useLauncherStatus() {
  return useQuery({
    queryKey: ['launcher', 'status'],
    queryFn: fetchLauncherStatus,
    staleTime: 60 * 1000,
    retry: false,
  })
}
