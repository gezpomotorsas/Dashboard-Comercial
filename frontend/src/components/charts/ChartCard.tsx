import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { DataStatusBadge } from '../dashboard/DataStatusBadge'
import type { DataStatus } from '../../types/dashboard'

interface ChartCardProps {
  title: string
  description?: string
  dataStatus?: DataStatus
  className?: string
  action?: ReactNode
  children: ReactNode
}

export function ChartCard({
  title,
  description,
  dataStatus,
  className,
  action,
  children,
}: ChartCardProps) {
  return (
    <section className={cn('rounded-[14px] border border-slate-200 bg-white p-5 shadow-sm', className)}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          {description ? <p className="text-sm text-slate-500">{description}</p> : null}
        </div>
        <div className="flex items-center gap-2">
          {action}
          {dataStatus ? <DataStatusBadge status={dataStatus} /> : null}
        </div>
      </div>
      {children}
    </section>
  )
}
