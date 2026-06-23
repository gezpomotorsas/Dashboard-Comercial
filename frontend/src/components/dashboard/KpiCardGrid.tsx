import type { DashboardKpiCard } from '@/types/dashboard'
import { KpiCard } from '@/components/dashboard/KpiCard'
import { KpiCardSkeleton } from '@/components/ui/KpiCardSkeleton'

interface KpiCardGridProps {
  cards?: DashboardKpiCard[]
  isLoading?: boolean
}

export function KpiCardGrid({ cards = [], isLoading }: KpiCardGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <KpiCardSkeleton key={index} />
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => (
        <KpiCard key={card.code} card={card} />
      ))}
    </div>
  )
}
