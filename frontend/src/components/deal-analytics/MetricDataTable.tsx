import type { ReactNode } from 'react'
import type { MetricColumn } from '@/lib/metricTooltips'
import { MetricTableLayout } from '@/components/ui/MetricTableLayout'

export function MetricDataTable({
  title,
  columns,
  rows,
  loading,
  description,
}: {
  title?: string
  description?: string
  columns: MetricColumn[]
  rows: Array<Array<string | number | ReactNode>>
  loading?: boolean
}) {
  if (loading) {
    return (
      <section className="rounded-xl border bg-white p-4 shadow-sm">
        <div className="h-48 animate-pulse rounded-lg bg-slate-100" />
      </section>
    )
  }

  return (
    <section className="rounded-xl border bg-white p-5 shadow-sm">
      {title ? (
        <>
          <h2 className="mb-1 text-lg font-medium text-slate-900">{title}</h2>
          {description ? (
            <p className="mb-4 text-sm leading-relaxed text-slate-500">{description}</p>
          ) : (
            <div className="mb-4" />
          )}
        </>
      ) : description ? (
        <p className="mb-4 text-sm leading-relaxed text-slate-500">{description}</p>
      ) : null}
      <MetricTableLayout columns={columns} rows={rows} />
      {rows.length === 0 && (
        <p className="py-8 text-center text-slate-500">Sin datos para los filtros actuales</p>
      )}
    </section>
  )
}
