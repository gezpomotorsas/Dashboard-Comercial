import { useMemo } from 'react'
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
import { MonthOverMonthBadge } from '@/components/deal-analytics/MonthOverMonthBadge'
import { ChartCard } from '@/components/charts/ChartCard'
import { MetricTableLayout } from '@/components/ui/MetricTableLayout'
import type { MetricColumn } from '@/lib/metricTooltips'
import type { GroupCompareRow, GroupPerformanceMetrics } from '@/types/advisorGroups'

const EMPTY_SUMMARY = {
  total_units: 0,
  units_this_month: 0,
  units_previous_month: 0,
  month_over_month_change_pct: null as number | null,
  this_month_key: '',
  previous_month_key: '',
}

const PERFORMANCE_COLUMNS: MetricColumn[] = [
  { label: 'Grupo', tooltip: 'Nombre del grupo comparado.', sticky: true, minWidth: 140 },
  { label: 'Ventas (mes)', tooltip: 'Cierres ganados en el mes calendario actual.', group: 'Ventas', align: 'right', minWidth: 96 },
  { label: 'Δ ventas', tooltip: 'Cambio de ventas vs el mes calendario anterior.', group: 'Ventas', align: 'center', minWidth: 130 },
  { label: 'Leads creados (mes)', tooltip: 'Negocios creados en el mes calendario actual.', group: 'Leads', align: 'right', minWidth: 110 },
  { label: 'Δ leads', tooltip: 'Leads creados vs el mes calendario anterior.', group: 'Leads', align: 'center', minWidth: 130 },
  {
    label: 'Tareas completadas (mes)',
    tooltip: 'Tareas marcadas como completadas en el mes calendario actual.',
    group: 'Tareas',
    align: 'right',
    minWidth: 130,
  },
  { label: 'Δ completadas', tooltip: 'Tareas completadas vs el mes calendario anterior.', group: 'Tareas', align: 'center', minWidth: 130 },
  {
    label: 'Tareas gestionadas (mes)',
    tooltip: 'Tareas nuevas asignadas (creadas) en el mes calendario actual.',
    group: 'Tareas',
    align: 'right',
    minWidth: 130,
  },
  { label: 'Δ gestionadas', tooltip: 'Tareas gestionadas vs el mes calendario anterior.', group: 'Tareas', align: 'center', minWidth: 130 },
  { label: 'Tareas venc.', tooltip: 'Tareas pendientes con fecha de vencimiento ya pasada.', group: 'Tareas', align: 'right', minWidth: 110 },
  { label: 'Δ tareas venc.', tooltip: 'Tareas vencidas con vencimiento en el mes vs mes anterior.', group: 'Tareas', align: 'center', minWidth: 130 },
  { label: 'Llamadas (mes)', tooltip: 'Llamadas realizadas en el mes calendario actual.', group: 'Contacto', align: 'right', minWidth: 110 },
  { label: 'Δ llamadas', tooltip: 'Llamadas vs el mes calendario anterior.', group: 'Contacto', align: 'center', minWidth: 130 },
  { label: 'WhatsApp (mes)', tooltip: 'Mensajes WhatsApp en el mes calendario actual.', group: 'Contacto', align: 'right', minWidth: 110 },
  { label: 'Δ WhatsApp', tooltip: 'WhatsApp vs el mes calendario anterior.', group: 'Contacto', align: 'center', minWidth: 130 },
]

function perf(g: GroupCompareRow): GroupPerformanceMetrics {
  return (
    g.performance ?? {
      won_sales: { ...EMPTY_SUMMARY, month_over_month_change_pct: 0 },
      leads_created: { ...EMPTY_SUMMARY },
      tasks_overdue: 0,
      tasks_overdue_monthly: { ...EMPTY_SUMMARY },
      tasks_completed_monthly: { ...EMPTY_SUMMARY },
      tasks_managed_monthly: { ...EMPTY_SUMMARY },
      calls_monthly: { ...EMPTY_SUMMARY },
      whatsapp_monthly: { ...EMPTY_SUMMARY },
    }
  )
}

function momBadge(summary: GroupPerformanceMetrics['won_sales']) {
  if (summary.units_this_month === 0 && summary.units_previous_month === 0) return '—'
  return <MonthOverMonthBadge summary={summary} />
}

export function GroupPerformanceCompare({ groups }: { groups: GroupCompareRow[] }) {
  const chartData = useMemo(
    () =>
      groups.map((g) => {
        const p = perf(g)
        return {
          name: g.group_name,
          sales_month: p.won_sales.units_this_month,
          leads_month: p.leads_created.units_this_month,
          tasks_completed: p.tasks_completed_monthly.units_this_month,
          tasks_managed: p.tasks_managed_monthly.units_this_month,
          tasks_overdue: p.tasks_overdue,
          calls: p.calls_monthly.units_this_month,
          whatsapp: p.whatsapp_monthly.units_this_month,
        }
      }),
    [groups],
  )

  const tableRows = useMemo(
    () =>
      groups.map((g) => {
        const p = perf(g)
        return [
          g.group_name,
          p.won_sales.units_this_month,
          momBadge(p.won_sales),
          p.leads_created.units_this_month,
          momBadge(p.leads_created),
          p.tasks_completed_monthly.units_this_month,
          momBadge(p.tasks_completed_monthly),
          p.tasks_managed_monthly.units_this_month,
          momBadge(p.tasks_managed_monthly),
          p.tasks_overdue,
          momBadge(p.tasks_overdue_monthly),
          p.calls_monthly.units_this_month,
          momBadge(p.calls_monthly),
          p.whatsapp_monthly.units_this_month,
          momBadge(p.whatsapp_monthly),
        ]
      }),
    [groups],
  )

  const height = Math.max(260, chartData.length * 56 + 48)

  if (groups.length === 0) return null

  return (
    <div className="space-y-6">
      <ChartCard
        title="Rendimiento operativo por grupo"
        description="Ventas, leads, tareas y contacto del mes calendario actual con variación mensual."
      >
        <MetricTableLayout columns={PERFORMANCE_COLUMNS} rows={tableRows} />
      </ChartCard>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Ventas y leads del mes" description="Unidades cerradas ganadas y negocios creados en el mes actual.">
          <div style={{ height }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="sales_month" name="Ventas (mes)" fill="#22c55e" radius={4} />
                <Bar dataKey="leads_month" name="Leads creados (mes)" fill="#2563eb" radius={4} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Tareas y contacto del mes" description="Tareas completadas, gestionadas, vencidas y contacto mensual.">
          <div style={{ height }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="tasks_completed" name="Tareas completadas (mes)" fill="#8b5cf6" radius={4} />
                <Bar dataKey="tasks_managed" name="Tareas gestionadas (mes)" fill="#a855f7" radius={4} />
                <Bar dataKey="tasks_overdue" name="Tareas vencidas" fill="#ef4444" radius={4} />
                <Bar dataKey="calls" name="Llamadas (mes)" fill="#0ea5e9" radius={4} />
                <Bar dataKey="whatsapp" name="WhatsApp (mes)" fill="#14b8a6" radius={4} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </div>
    </div>
  )
}
