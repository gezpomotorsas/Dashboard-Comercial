import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Filter, X } from 'lucide-react'
import { MetricTableHeader } from '@/components/ui/MetricTableHeader'
import { ADVISOR_TASK_COLUMNS } from '@/lib/metricTooltips'
import { cn } from '@/lib/utils'
import type { AdvisorPortfolioTask } from '@/types/dealAnalytics'

const PAGE_SIZE = 20
const EMPTY = '—'

type TaskColumnKey =
  | 'subject'
  | 'contact'
  | 'deal'
  | 'stage'
  | 'status'
  | 'priority'
  | 'due'
  | 'days'

const COLUMN_KEYS: TaskColumnKey[] = [
  'subject',
  'contact',
  'deal',
  'stage',
  'status',
  'priority',
  'due',
  'days',
]

const COLUMN_ALIGN: Record<TaskColumnKey, 'left' | 'right'> = {
  subject: 'left',
  contact: 'left',
  deal: 'left',
  stage: 'left',
  status: 'left',
  priority: 'left',
  due: 'right',
  days: 'right',
}

function taskFlag(value: unknown): boolean {
  return value === true || value === 'true'
}

function formatTaskDueDate(iso: string | null | undefined): string {
  if (!iso) return EMPTY
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return EMPTY
  return date.toLocaleDateString('es-CO', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

function formatTaskStage(task: AdvisorPortfolioTask): string {
  if (task.deal_stage_label) return task.deal_stage_label
  if (task.deal_id) return EMPTY
  if (task.contact_id) return 'Solo contacto'
  return EMPTY
}

function formatTaskStatus(task: AdvisorPortfolioTask): string {
  const completed = taskFlag(task.is_completed)
  const overdue = taskFlag(task.is_overdue)
  const completedLate = taskFlag(task.is_completed_late)
  if (completed) {
    return completedLate ? 'Completada (atrasada)' : task.status_label
  }
  if (overdue) {
    return `${task.status_label} (vencida)`
  }
  return task.status_label
}

function formatDaysUnresolved(task: AdvisorPortfolioTask): string {
  if (task.days_unresolved == null) return EMPTY
  return String(task.days_unresolved)
}

function getTaskCellValue(task: AdvisorPortfolioTask, key: TaskColumnKey): string {
  switch (key) {
    case 'subject':
      return task.subject?.trim() || EMPTY
    case 'contact':
      return task.contact_name?.trim() || EMPTY
    case 'deal':
      return task.deal_name?.trim() || EMPTY
    case 'stage':
      return formatTaskStage(task)
    case 'status':
      return formatTaskStatus(task)
    case 'priority':
      return task.priority?.trim() || EMPTY
    case 'due':
      return formatTaskDueDate(task.due_at)
    case 'days':
      return formatDaysUnresolved(task)
    default:
      return EMPTY
  }
}

function buildUniqueValues(tasks: AdvisorPortfolioTask[]): Record<TaskColumnKey, string[]> {
  const sets: Record<TaskColumnKey, Set<string>> = {
    subject: new Set(),
    contact: new Set(),
    deal: new Set(),
    stage: new Set(),
    status: new Set(),
    priority: new Set(),
    due: new Set(),
    days: new Set(),
  }
  for (const task of tasks) {
    for (const key of COLUMN_KEYS) {
      sets[key].add(getTaskCellValue(task, key))
    }
  }
  const result = {} as Record<TaskColumnKey, string[]>
  for (const key of COLUMN_KEYS) {
    result[key] = Array.from(sets[key]).sort((a, b) => {
      if (key === 'days') {
        const na = a === EMPTY ? -1 : Number(a)
        const nb = b === EMPTY ? -1 : Number(b)
        if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb
      }
      if (key === 'due') {
        if (a === EMPTY) return 1
        if (b === EMPTY) return -1
      }
      return a.localeCompare(b, 'es-CO')
    })
  }
  return result
}

function applyColumnFilters(
  tasks: AdvisorPortfolioTask[],
  filters: Partial<Record<TaskColumnKey, Set<string>>>,
): AdvisorPortfolioTask[] {
  const active = Object.entries(filters).filter(
    ([, values]) => values && values.size > 0,
  ) as Array<[TaskColumnKey, Set<string>]>
  if (active.length === 0) return tasks
  return tasks.filter((task) =>
    active.every(([key, allowed]) => allowed.has(getTaskCellValue(task, key))),
  )
}

function ColumnFilterPopover({
  columnKey,
  label,
  options,
  selected,
  onChange,
  onClose,
}: {
  columnKey: TaskColumnKey
  label: string
  options: string[]
  selected: Set<string>
  onChange: (next: Set<string>) => void
  onClose: () => void
}) {
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [onClose])

  const filteredOptions = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return options
    return options.filter((opt) => opt.toLowerCase().includes(q))
  }, [options, search])

  function toggle(value: string) {
    const next = new Set(selected)
    if (next.has(value)) next.delete(value)
    else next.add(value)
    onChange(next)
  }

  const isActive = selected.size < options.length

  return (
    <div
      ref={ref}
      className="absolute left-0 top-full z-40 mt-1 w-64 rounded-lg border border-slate-200 bg-white p-3 shadow-lg"
      role="dialog"
      aria-label={`Filtrar ${label}`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-slate-700">Incluir valores</p>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          aria-label="Cerrar filtro"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <input
        type="search"
        placeholder="Buscar…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-2 w-full rounded border border-slate-200 px-2 py-1.5 text-xs"
      />
      <div className="mb-2 flex flex-wrap gap-1">
        <button
          type="button"
          className="rounded border px-2 py-0.5 text-[11px] hover:bg-slate-50"
          onClick={() => onChange(new Set(options))}
        >
          Todos
        </button>
        <button
          type="button"
          className="rounded border px-2 py-0.5 text-[11px] hover:bg-slate-50"
          onClick={() => onChange(new Set())}
        >
          Ninguno
        </button>
        <button
          type="button"
          className="rounded border px-2 py-0.5 text-[11px] hover:bg-slate-50"
          onClick={() => onChange(new Set(options.filter((o) => !selected.has(o))))}
        >
          Invertir
        </button>
      </div>
      <div className="max-h-52 space-y-1 overflow-y-auto text-xs">
        {filteredOptions.length === 0 ? (
          <p className="py-2 text-center text-slate-400">Sin coincidencias</p>
        ) : (
          filteredOptions.map((opt) => (
            <label
              key={opt}
              className="flex cursor-pointer items-start gap-2 rounded px-1 py-0.5 hover:bg-slate-50"
            >
              <input
                type="checkbox"
                className="mt-0.5 shrink-0"
                checked={selected.has(opt)}
                onChange={() => toggle(opt)}
              />
              <span
                className={cn(
                  'min-w-0 flex-1 break-words',
                  columnKey === 'days' || columnKey === 'due' ? 'tabular-nums' : '',
                )}
              >
                {opt}
              </span>
            </label>
          ))
        )}
      </div>
      {isActive ? (
        <p className="mt-2 border-t pt-2 text-[11px] text-blue-600">
          {selected.size.toLocaleString('es-CO')} de {options.length.toLocaleString('es-CO')} incluidos
        </p>
      ) : null}
    </div>
  )
}

export function AdvisorTaskTable({
  tasks,
  resetKey,
}: {
  tasks: AdvisorPortfolioTask[]
  resetKey?: string | number
}) {
  const [page, setPage] = useState(0)
  const [columnFilters, setColumnFilters] = useState<Partial<Record<TaskColumnKey, Set<string>>>>({})
  const [openFilter, setOpenFilter] = useState<TaskColumnKey | null>(null)

  const uniqueValues = useMemo(() => buildUniqueValues(tasks), [tasks])

  const filteredTasks = useMemo(
    () => applyColumnFilters(tasks, columnFilters),
    [tasks, columnFilters],
  )

  useLayoutEffect(() => {
    setPage(0)
    setColumnFilters({})
    setOpenFilter(null)
  }, [resetKey])

  const totalPages = Math.max(1, Math.ceil(filteredTasks.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages - 1)
  const pageTasks = filteredTasks.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE)
  const from = filteredTasks.length === 0 ? 0 : safePage * PAGE_SIZE + 1
  const to = Math.min(filteredTasks.length, (safePage + 1) * PAGE_SIZE)

  function getSelectedSet(key: TaskColumnKey): Set<string> {
    return columnFilters[key] ?? new Set(uniqueValues[key])
  }

  function isColumnFilterActive(key: TaskColumnKey): boolean {
    const selected = columnFilters[key]
    return Boolean(selected && selected.size < uniqueValues[key].length)
  }

  function setColumnSelection(key: TaskColumnKey, next: Set<string>) {
    if (next.size === uniqueValues[key].length) {
      setColumnFilters((prev) => {
        const copy = { ...prev }
        delete copy[key]
        return copy
      })
      return
    }
    setColumnFilters((prev) => ({ ...prev, [key]: next }))
    setPage(0)
  }

  const activeFilterCount = COLUMN_KEYS.filter(isColumnFilterActive).length

  return (
    <div className="overflow-x-auto">
      {activeFilterCount > 0 ? (
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">
          <span>
            {activeFilterCount} filtro{activeFilterCount === 1 ? '' : 's'} de columna activo
            {activeFilterCount === 1 ? '' : 's'}
          </span>
          <button
            type="button"
            className="rounded border px-2 py-1 hover:bg-slate-50"
            onClick={() => {
              setColumnFilters({})
              setOpenFilter(null)
              setPage(0)
            }}
          >
            Limpiar filtros de columna
          </button>
        </div>
      ) : null}

      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b text-left text-slate-500">
            <th className="w-10 px-2 py-2 text-center font-medium">#</th>
            {COLUMN_KEYS.map((key, index) => {
              const col = ADVISOR_TASK_COLUMNS[index]
              const align = COLUMN_ALIGN[key]
              return (
                <th
                  key={key}
                  className={cn(
                    'relative px-2 py-2 font-medium',
                    align === 'right' && 'text-right',
                    key === 'due' && 'min-w-[6.5rem]',
                    key === 'days' && 'min-w-[5.5rem]',
                  )}
                >
                  <div
                    className={cn(
                      'inline-flex items-start gap-1',
                      align === 'right' && 'justify-end',
                    )}
                  >
                    <MetricTableHeader
                      as="span"
                      label={col.label}
                      tooltip={col.tooltip}
                      className={align === 'right' ? 'text-right' : undefined}
                    />
                    <button
                      type="button"
                      onClick={() => setOpenFilter(openFilter === key ? null : key)}
                      className={cn(
                        'mt-0.5 shrink-0 rounded p-0.5',
                        isColumnFilterActive(key)
                          ? 'bg-blue-100 text-blue-700'
                          : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600',
                      )}
                      aria-label={`Filtrar columna ${col.label}`}
                    >
                      <Filter className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  {openFilter === key ? (
                    <ColumnFilterPopover
                      columnKey={key}
                      label={col.label}
                      options={uniqueValues[key]}
                      selected={getSelectedSet(key)}
                      onChange={(next) => setColumnSelection(key, next)}
                      onClose={() => setOpenFilter(null)}
                    />
                  ) : null}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {pageTasks.map((task, i) => (
            <tr key={task.task_id} className="border-b hover:bg-slate-50">
              <td className="px-2 py-2 text-center tabular-nums text-slate-400">{from + i}</td>
              {COLUMN_KEYS.map((key) => {
                const value = getTaskCellValue(task, key)
                const align = COLUMN_ALIGN[key]
                return (
                  <td
                    key={key}
                    className={cn(
                      'px-2 py-2',
                      align === 'right' && 'text-right tabular-nums whitespace-nowrap',
                      key === 'due' && 'font-mono text-[13px]',
                      key === 'days' && 'font-semibold',
                    )}
                  >
                    {value}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {filteredTasks.length === 0 ? (
        <p className="py-8 text-center text-slate-500">Sin datos para los filtros actuales</p>
      ) : (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-3 text-sm text-slate-600">
          <span>
            Mostrando {from}–{to} de {filteredTasks.length.toLocaleString('es-CO')}
            {filteredTasks.length !== tasks.length
              ? ` (de ${tasks.length.toLocaleString('es-CO')} tras filtros superiores)`
              : ''}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={safePage <= 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="rounded-lg border px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-slate-50"
            >
              Anterior
            </button>
            <span className="min-w-[7rem] text-center">
              Página {safePage + 1} / {totalPages}
            </span>
            <button
              type="button"
              disabled={safePage >= totalPages - 1}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              className="rounded-lg border px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-slate-50"
            >
              Siguiente
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
