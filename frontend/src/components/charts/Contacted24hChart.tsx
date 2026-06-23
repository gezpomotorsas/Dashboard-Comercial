import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Contacted24hBrandRow } from '../../types/dashboard'
import { ChartCard } from './ChartCard'
import { EmptyState } from '../ui/EmptyState'

interface Contacted24hChartProps {
  data: Contacted24hBrandRow[]
}

export function Contacted24hChart({ data }: Contacted24hChartProps) {
  const chartData = data.map((row) => ({
    ...row,
    rate: row.data_status === 'unavailable' ? null : row.contacted_within_24h_rate,
  }))
  const hasData = data.some(
    (row) =>
      row.data_status !== 'unavailable' && row.contacted_within_24h_rate != null,
  )
  const aggregateStatus = data.some((row) => row.data_status === 'available')
    ? 'available'
    : data.some((row) => row.data_status === 'partial')
      ? 'partial'
      : 'unavailable'

  return (
    <ChartCard
      title="Contactados antes de 24 horas"
      description="Porcentaje por marca"
      dataStatus={aggregateStatus}
    >
      {hasData ? (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="brand_label" tick={{ fill: '#64748b', fontSize: 12 }} />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: '#64748b', fontSize: 12 }}
              tickFormatter={(value: number) => `${value}%`}
            />
            <Tooltip
              formatter={(value) =>
                typeof value === 'number' ? `${value.toFixed(1)}%` : 'Sin datos'
              }
            />
            <Bar dataKey="rate" name="% < 24h" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState message="No hay datos de contacto en 24h para las marcas seleccionadas." />
      )}
    </ChartCard>
  )
}
