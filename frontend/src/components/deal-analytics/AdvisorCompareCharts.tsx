import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { BrandAdvisorRow } from '@/types/dealAnalytics'
import { ChartCard } from '@/components/charts/ChartCard'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/EmptyState'
import { advisorPortfolioPath } from '@/lib/advisorRoutes'
import { staleChartSeriesLabel } from '@/lib/brandStale'
import { formatPercent } from '@/lib/format'

const DEFAULT_TOP_N = 6

const COLORS = {
  open: '#2563eb',
  new7: '#14b8a6',
  new30: '#8b5cf6',
  callCoverage: '#2563eb',
  waCoverage: '#22c55e',
  combinedCoverage: '#8b5cf6',
  overdueContact: '#f97316',
  stale: '#f97316',
  dealsOverdue: '#ef4444',
  tasksDone: '#22c55e',
  tasksOpen: '#64748b',
  tasksOverdue: '#f59e0b',
} as const

function advisorKey(row: BrandAdvisorRow): string {
  return row.owner_id ?? 'unassigned'
}

function advisorLabel(row: BrandAdvisorRow): string {
  return row.owner_name ?? 'Sin asignar'
}

type ChartRow = {
  key: string
  name: string
  open_deals: number
  new_deals_7d: number
  new_deals_30d: number
  call_coverage_rate: number
  whatsapp_coverage_rate: number
  combined_coverage_rate: number
  overdue_contact_21d: number
  stale_45d_open: number
  deals_with_overdue_tasks: number
  tasks_completed: number
  tasks_open: number
  tasks_overdue: number
}

function toChartRow(row: BrandAdvisorRow): ChartRow {
  return {
    key: advisorKey(row),
    name: advisorLabel(row),
    open_deals: row.open_deals,
    new_deals_7d: row.new_deals_7d,
    new_deals_30d: row.new_deals_30d,
    call_coverage_rate: row.call_coverage_rate ?? 0,
    whatsapp_coverage_rate: row.whatsapp_coverage_rate ?? 0,
    combined_coverage_rate: row.combined_coverage_rate ?? 0,
    overdue_contact_21d: row.overdue_contact_21d ?? 0,
    stale_45d_open: row.stale_45d_open,
    deals_with_overdue_tasks: row.deals_with_overdue_tasks,
    tasks_completed: row.tasks_completed,
    tasks_open: row.tasks_open,
    tasks_overdue: row.tasks_overdue,
  }
}

function topAdvisorKeys(advisors: BrandAdvisorRow[], n: number): string[] {
  return [...advisors]
    .sort((a, b) => b.open_deals - a.open_deals || advisorLabel(a).localeCompare(advisorLabel(b)))
    .slice(0, n)
    .map(advisorKey)
}

export function AdvisorCompareCharts({
  advisors,
  brandKey,
  brandLabel,
  staleDays,
}: {
  advisors: BrandAdvisorRow[]
  brandKey: string
  brandLabel: string
  staleDays?: number
}) {
  const staleSeriesLabel = staleChartSeriesLabel(brandKey, staleDays)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set(topAdvisorKeys(advisors, DEFAULT_TOP_N)))

  useEffect(() => {
    setSelectedIds(new Set(topAdvisorKeys(advisors, DEFAULT_TOP_N)))
  }, [brandKey, advisors])

  const sortedAdvisors = useMemo(
    () =>
      [...advisors].sort(
        (a, b) => b.open_deals - a.open_deals || advisorLabel(a).localeCompare(advisorLabel(b)),
      ),
    [advisors],
  )

  const chartData = useMemo(() => {
    const selected = sortedAdvisors.filter((row) => selectedIds.has(advisorKey(row)))
    return selected.map(toChartRow)
  }, [sortedAdvisors, selectedIds])

  const chartHeight = Math.max(260, chartData.length * 52 + 48)

  function toggleAdvisor(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function selectTop(n: number) {
    setSelectedIds(new Set(topAdvisorKeys(advisors, n)))
  }

  if (advisors.length === 0) {
    return null
  }

  return (
    <section className="space-y-4 rounded-xl border bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-medium text-slate-900">Comparativa visual de asesores — {brandLabel}</h2>
        <p className="mt-1 text-sm text-slate-500">
          Elige quiénes comparar y revisa cartera, cobertura de contacto y tareas en gráficas.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 pb-4">
        <Button type="button" variant="outline" className="px-3 py-1.5 text-xs" onClick={() => selectTop(6)}>
          Top 6 cartera
        </Button>
        <Button
          type="button"
          variant="outline"
          className="px-3 py-1.5 text-xs"
          onClick={() => setSelectedIds(new Set(advisors.map(advisorKey)))}
        >
          Todos ({advisors.length})
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="px-3 py-1.5 text-xs"
          onClick={() => setSelectedIds(new Set())}
        >
          Limpiar
        </Button>
        <span className="text-xs text-slate-400">
          {selectedIds.size} de {advisors.length} seleccionados
        </span>
      </div>

      <div className="flex max-h-48 flex-wrap gap-2 overflow-y-auto rounded-lg border border-slate-100 bg-slate-50 p-3">
        {sortedAdvisors.map((row) => {
          const id = advisorKey(row)
          const active = selectedIds.has(id)
          const path = advisorPortfolioPath(brandKey, row.owner_id)
          return (
            <div
              key={id}
              className={`inline-flex items-center overflow-hidden rounded-full text-xs font-medium transition-colors ${
                active
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'border border-slate-200 bg-white text-slate-600'
              }`}
            >
              <Link
                to={path}
                className={`px-3 py-1.5 hover:underline ${
                  active ? 'text-white hover:text-blue-100' : 'text-blue-600 hover:text-blue-800'
                }`}
                title={`Ver cartera de ${advisorLabel(row)}`}
              >
                {advisorLabel(row)}
              </Link>
              <button
                type="button"
                onClick={() => toggleAdvisor(id)}
                className={`border-l px-2 py-1.5 ${
                  active ? 'border-blue-500 text-blue-100' : 'border-slate-200 text-slate-500'
                }`}
                title={active ? 'Quitar de la comparativa' : 'Incluir en la comparativa'}
              >
                {row.open_deals}
              </button>
            </div>
          )
        })}
      </div>

      {chartData.length === 0 ? (
        <EmptyState message="Selecciona al menos un asesor para ver la comparativa." />
      ) : (
        <div className="grid gap-6 xl:grid-cols-1">
          <ChartCard
            title="Cartera y negocios nuevos"
            description="Volumen operativo: cuántos negocios abiertos tiene cada asesor y cuántos creó recientemente."
          >
            <CompareBarChart
              data={chartData}
              height={chartHeight}
              brandKey={brandKey}
              bars={[
                { key: 'open_deals', name: 'Abiertos', fill: COLORS.open },
                { key: 'new_deals_7d', name: 'Nuevos 7d', fill: COLORS.new7 },
                { key: 'new_deals_30d', name: 'Nuevos 30d', fill: COLORS.new30 },
              ]}
            />
          </ChartCard>

          <ChartCard
            title="Cobertura de contacto (21d)"
            description="Porcentaje de negocios activos contactados por llamada, WhatsApp o ambos. Atrasados = sin contacto en 21d."
          >
            <CompareBarChart
              data={chartData}
              height={chartHeight}
              brandKey={brandKey}
              bars={[
                { key: 'call_coverage_rate', name: 'Cob. llamadas (%)', fill: COLORS.callCoverage, isPercent: true },
                { key: 'whatsapp_coverage_rate', name: 'Cob. WhatsApp (%)', fill: COLORS.waCoverage, isPercent: true },
                { key: 'combined_coverage_rate', name: 'Cob. combinada (%)', fill: COLORS.combinedCoverage, isPercent: true },
                { key: 'overdue_contact_21d', name: 'Atrasados 21d', fill: COLORS.overdueContact },
              ]}
            />
          </ChartCard>

          <ChartCard
            title="Señales de riesgo en cartera"
            description={`${staleSeriesLabel} y negocios con tareas vencidas — a menor, mejor.`}
          >
            <CompareBarChart
              data={chartData}
              height={chartHeight}
              brandKey={brandKey}
              bars={[
                { key: 'stale_45d_open', name: staleSeriesLabel, fill: COLORS.stale },
                { key: 'deals_with_overdue_tasks', name: 'Neg. c/ tareas venc.', fill: COLORS.dealsOverdue },
              ]}
            />
          </ChartCard>

          <ChartCard
            title="Disciplina de tareas"
            description="Tareas completadas vs pendientes y vencidas vinculadas a los negocios del asesor."
          >
            <CompareBarChart
              data={chartData}
              height={chartHeight}
              brandKey={brandKey}
              bars={[
                { key: 'tasks_completed', name: 'Completadas', fill: COLORS.tasksDone },
                { key: 'tasks_open', name: 'Abiertas', fill: COLORS.tasksOpen },
                { key: 'tasks_overdue', name: 'Vencidas', fill: COLORS.tasksOverdue },
              ]}
            />
          </ChartCard>
        </div>
      )}
    </section>
  )
}

function CompareBarChart({
  data,
  height,
  bars,
  brandKey,
}: {
  data: ChartRow[]
  height: number
  brandKey: string
  bars: Array<{ key: keyof ChartRow; name: string; fill: string; isPercent?: boolean }>
}) {
  const nameToKey = useMemo(() => new Map(data.map((row) => [row.name, row.key])), [data])

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
        <XAxis
          type="number"
          allowDecimals={bars.some((b) => b.isPercent)}
          tick={{ fill: '#64748b', fontSize: 11 }}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={128}
          tick={(props) => <AdvisorAxisTick {...props} brandKey={brandKey} nameToKey={nameToKey} />}
        />
        <Tooltip
          formatter={(value, name) => {
            const bar = bars.find((b) => b.name === name)
            const num = typeof value === 'number' ? value : Number(value)
            if (bar?.isPercent) return formatPercent(num)
            return num.toLocaleString('es-CO')
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {bars.map((bar) => (
          <Bar key={bar.key} dataKey={bar.key} name={bar.name} fill={bar.fill} radius={[0, 4, 4, 0]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

function AdvisorAxisTick({
  x,
  y,
  payload,
  brandKey,
  nameToKey,
}: {
  x?: string | number
  y?: string | number
  payload?: { value: string }
  brandKey: string
  nameToKey: Map<string, string>
}) {
  const navigate = useNavigate()
  const name = payload?.value ?? ''
  const ownerKey = nameToKey.get(name)
  const label = name.length > 24 ? `${name.slice(0, 22)}…` : name
  const tx = typeof x === 'number' ? x : Number(x ?? 0)
  const ty = typeof y === 'number' ? y : Number(y ?? 0)

  return (
    <g transform={`translate(${tx},${ty})`}>
      <text
        x={-4}
        y={0}
        dy={4}
        textAnchor="end"
        fill="#2563eb"
        fontSize={11}
        style={{ cursor: ownerKey ? 'pointer' : 'default' }}
        onClick={() => {
          if (ownerKey) navigate(advisorPortfolioPath(brandKey, ownerKey === 'unassigned' ? null : ownerKey))
        }}
      >
        {label}
      </text>
    </g>
  )
}
