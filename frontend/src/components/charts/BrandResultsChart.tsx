import {
  Bar,
  CartesianGrid,
  Legend,
  BarChart as RechartsBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { BrandResultRow } from '../../types/dashboard'
import { ChartCard } from './ChartCard'
import { EmptyState } from '../ui/EmptyState'

interface BrandResultsChartProps {
  data: BrandResultRow[]
}

export function BrandResultsChart({ data }: BrandResultsChartProps) {
  const chartData = data.map((row) => ({
    ...row,
    leads: row.leads_data_status === 'unavailable' ? null : row.leads_created,
  }))
  const hasData = data.some((row) => (row.leads_created ?? 0) > 0 || row.deals_created > 0 || row.won_deals > 0)

  return (
    <ChartCard
      title="Resultados por marca"
      description="Leads, negocios creados y ganados"
      dataStatus="available"
    >
      {hasData ? (
        <ResponsiveContainer width="100%" height={280}>
          <RechartsBarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="brand_label" tick={{ fill: '#64748b', fontSize: 12 }} />
            <YAxis tick={{ fill: '#64748b', fontSize: 12 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="leads" name="Leads" fill="#2563eb" radius={[4, 4, 0, 0]} />
            <Bar dataKey="deals_created" name="Negocios" fill="#38bdf8" radius={[4, 4, 0, 0]} />
            <Bar dataKey="won_deals" name="Ganados" fill="#10b981" radius={[4, 4, 0, 0]} />
          </RechartsBarChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState message="No hay resultados por marca para los filtros actuales." />
      )}
    </ChartCard>
  )
}
