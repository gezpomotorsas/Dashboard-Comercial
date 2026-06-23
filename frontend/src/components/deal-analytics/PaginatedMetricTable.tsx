import { useLayoutEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { MetricColumn } from '@/lib/metricTooltips'
import { MetricTableLayout } from '@/components/ui/MetricTableLayout'

const DEFAULT_PAGE_SIZE = 20

export function PaginatedMetricTable({
  title,
  columns,
  rows,
  loading,
  description,
  pageSize = DEFAULT_PAGE_SIZE,
  resetKey,
}: {
  title?: string
  description?: string
  columns: MetricColumn[]
  rows: Array<Array<string | number | ReactNode>>
  loading?: boolean
  pageSize?: number
  /** Cambia al filtrar para volver a la página 1 */
  resetKey?: string | number
}) {
  const [page, setPage] = useState(0)

  useLayoutEffect(() => {
    setPage(0)
  }, [resetKey])

  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize))
  const safePage = Math.min(page, totalPages - 1)
  const pageRows = useMemo(
    () => rows.slice(safePage * pageSize, safePage * pageSize + pageSize),
    [rows, safePage, pageSize],
  )
  const from = rows.length === 0 ? 0 : safePage * pageSize + 1
  const to = Math.min(rows.length, (safePage + 1) * pageSize)

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

      <MetricTableLayout columns={columns} rows={pageRows} rowNumberFrom={from} />

      {rows.length === 0 ? (
        <p className="py-8 text-center text-slate-500">Sin datos para los filtros actuales</p>
      ) : (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 text-sm text-slate-600">
          <span>
            Mostrando {from}–{to} de {rows.length.toLocaleString('es-CO')} asesores
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={safePage <= 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="rounded-lg border border-slate-200 px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-slate-50"
            >
              Anterior
            </button>
            <span className="min-w-[7rem] text-center tabular-nums">
              Página {safePage + 1} / {totalPages}
            </span>
            <button
              type="button"
              disabled={safePage >= totalPages - 1}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              className="rounded-lg border border-slate-200 px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-slate-50"
            >
              Siguiente
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
