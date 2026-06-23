import type { ReactNode } from 'react'
import type { MetricColumn } from '@/lib/metricTooltips'
import { MetricTableHeader } from '@/components/ui/MetricTableHeader'
import { cn } from '@/lib/utils'

function columnStyle(col: MetricColumn) {
  return col.minWidth ? { minWidth: col.minWidth } : undefined
}

function headerCellClass(col: MetricColumn) {
  return cn(
    'whitespace-nowrap px-3 py-2.5 align-bottom',
    col.group === 'Ventas' && 'bg-emerald-50/80',
    col.sticky && 'sticky left-0 z-20 bg-white shadow-[4px_0_8px_-4px_rgba(15,23,42,0.12)]',
  )
}

function bodyCellClass(col: MetricColumn) {
  return cn(
    'px-3 py-3 align-middle text-slate-800',
    col.align === 'right' && 'text-right tabular-nums',
    col.align === 'center' && 'text-center tabular-nums',
    col.group === 'Ventas' && 'bg-emerald-50/40',
    col.sticky && 'sticky left-0 z-10 bg-white font-medium shadow-[4px_0_8px_-4px_rgba(15,23,42,0.08)] group-hover:bg-slate-50',
  )
}

function buildGroupSpans(columns: MetricColumn[]): Array<{ label: string; span: number }> {
  const spans: Array<{ label: string; span: number }> = []
  for (const col of columns) {
    const label = col.group ?? ''
    const last = spans[spans.length - 1]
    if (last && last.label === label) {
      last.span += 1
    } else {
      spans.push({ label, span: 1 })
    }
  }
  return spans
}

export function MetricTableLayout({
  columns,
  rows,
  rowNumberFrom,
}: {
  columns: MetricColumn[]
  rows: Array<Array<string | number | ReactNode>>
  rowNumberFrom?: number
}) {
  const hasGroups = columns.some((col) => col.group)
  const groupSpans = hasGroups ? buildGroupSpans(columns) : []

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full min-w-[72rem] border-collapse text-sm">
        <thead className="bg-slate-50/90">
          {hasGroups ? (
            <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-500">
              {rowNumberFrom != null ? (
                <th
                  className="sticky left-0 z-20 w-12 bg-slate-50/90 px-3 py-2"
                  aria-hidden={!hasGroups}
                />
              ) : null}
              {groupSpans.map((group, index) => (
                <th
                  key={`${group.label}-${index}`}
                  colSpan={group.span}
                  className={cn(
                    'px-3 py-2 text-left',
                    group.label === 'Ventas' && 'bg-emerald-100/70 text-emerald-800',
                    group.label === 'Leads' && 'bg-blue-100/70 text-blue-800',
                    group.label === 'Contacto' && 'text-blue-700',
                    group.label === 'Tareas' && 'text-amber-800',
                    group.label === 'Cartera' && 'text-slate-600',
                  )}
                >
                  {group.label || (index === 0 ? ' ' : '')}
                </th>
              ))}
            </tr>
          ) : null}
          <tr className="border-b border-slate-200 text-left text-slate-600">
            {rowNumberFrom != null ? (
              <th className="sticky left-0 z-20 w-12 bg-slate-50/90 px-3 py-2.5 text-xs font-medium text-slate-400">
                #
              </th>
            ) : null}
            {columns.map((col) => (
              <th
                key={col.label}
                className={headerCellClass(col)}
                style={columnStyle(col)}
              >
                <MetricTableHeader
                  as="span"
                  label={col.label}
                  tooltip={col.tooltip}
                  className="text-xs"
                />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="group border-b border-slate-100 last:border-0 hover:bg-slate-50/80">
              {rowNumberFrom != null ? (
                <td className="sticky left-0 z-10 bg-white px-3 py-3 text-xs tabular-nums text-slate-400 group-hover:bg-slate-50">
                  {rowNumberFrom + rowIndex}
                </td>
              ) : null}
              {row.map((cell, cellIndex) => {
                const col = columns[cellIndex]
                return (
                  <td
                    key={cellIndex}
                    className={bodyCellClass(col)}
                    style={columnStyle(col)}
                  >
                    {cell}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
