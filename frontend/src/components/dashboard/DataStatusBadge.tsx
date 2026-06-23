import type { DataStatus } from '@/types/dashboard'
import { Badge } from '@/components/ui/badge'

interface DataStatusBadgeProps {
  status: DataStatus
  reason?: string | null
}

export function DataStatusBadge({ status, reason }: DataStatusBadgeProps) {
  if (status === 'available') return null

  const label = status === 'partial' ? 'Datos parciales' : 'No disponible'
  const variant = status === 'partial' ? 'warning' : 'muted'

  return (
    <Badge variant={variant} title={reason ?? undefined}>
      {label}
    </Badge>
  )
}
