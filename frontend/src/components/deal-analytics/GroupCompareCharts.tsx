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
import type { GroupCompareRow } from '@/types/advisorGroups'
import { ChartCard } from '@/components/charts/ChartCard'
import { formatPercent } from '@/lib/format'

const COLORS = {
  open: '#2563eb',
  stale: '#f97316',
  callCoverage: '#2563eb',
  waCoverage: '#22c55e',
  combinedCoverage: '#8b5cf6',
  overdueContact: '#ef4444',
} as const

function groupCoverage(g: GroupCompareRow) {
  const cm = g.contact_methodology
  return {
    call_coverage_rate: cm?.calls?.call_coverage_rate ?? 0,
    whatsapp_coverage_rate: cm?.whatsapp?.whatsapp_coverage_rate ?? 0,
    combined_coverage_rate: cm?.coverage?.combined_contact_coverage_rate ?? 0,
    overdue_contact_21d: cm?.coverage?.overdue_contact_21d ?? 0,
  }
}

export function GroupCompareCharts({ groups }: { groups: GroupCompareRow[] }) {
  const chartData = useMemo(
    () =>
      groups.map((g) => ({
        name: g.group_name,
        open_deals: g.open_deals,
        stale_45d_open: g.stale_45d_open,
        ...groupCoverage(g),
      })),
    [groups],
  )

  const chartHeight = Math.max(240, chartData.length * 64 + 40)

  if (groups.length === 0) {
    return null
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <ChartCard
        title="Cartera abierta por grupo"
        description="Negocios abiertos y estancados 45+ días por grupo de asesores."
      >
        <div style={{ height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="open_deals" name="Abiertos" fill={COLORS.open} radius={4} />
              <Bar dataKey="stale_45d_open" name="Estancados 45d" fill={COLORS.stale} radius={4} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>

      <ChartCard
        title="Cobertura de contacto por grupo"
        description="Agregación desde registros base (no promedio de %). Ventana 21d."
      >
        <div style={{ height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10 }} />
              <Tooltip
                formatter={(value, name) => {
                  if (typeof name === 'string' && name.includes('%')) return formatPercent(Number(value))
                  return value
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="call_coverage_rate" name="Cob. llamadas %" fill={COLORS.callCoverage} radius={4} />
              <Bar dataKey="whatsapp_coverage_rate" name="Cob. WhatsApp %" fill={COLORS.waCoverage} radius={4} />
              <Bar dataKey="combined_coverage_rate" name="Cob. combinada %" fill={COLORS.combinedCoverage} radius={4} />
              <Bar dataKey="overdue_contact_21d" name="Atrasados 21d" fill={COLORS.overdueContact} radius={4} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>
    </div>
  )
}
