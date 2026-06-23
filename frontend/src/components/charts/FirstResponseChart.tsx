import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { FirstResponseBrandRow } from '../../types/dashboard'
import { formatDurationMinutes } from '../../lib/format'
import { ChartCard } from './ChartCard'
import { EmptyState } from '../ui/EmptyState'

interface FirstResponseChartProps {
  data: FirstResponseBrandRow[]
}

export function FirstResponseChart({ data }: FirstResponseChartProps) {
  const chartData = data.map((row) => ({
    ...row,
    average:
      row.data_status === 'unavailable' ? null : row.average_first_response_minutes,
  }))
  const hasData = data.some(
    (row) =>
      row.data_status !== 'unavailable' && row.average_first_response_minutes != null,
  )
  const aggregateStatus = data.some((row) => row.data_status === 'available')
    ? 'available'
    : data.some((row) => row.data_status === 'partial')
      ? 'partial'
      : 'unavailable'

  return (
    <ChartCard
      title="Tiempo de primera respuesta"
      description="Promedio por marca (menor es mejor)"
      dataStatus={aggregateStatus}
    >
      {hasData ? (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="brand_label" tick={{ fill: '#64748b', fontSize: 12 }} />
            <YAxis
              tick={{ fill: '#64748b', fontSize: 12 }}
              tickFormatter={(value: number) => formatDurationMinutes(value) ?? ''}
            />
            <Tooltip
              formatter={(value) =>
                typeof value === 'number' ? formatDurationMinutes(value) ?? 'Sin datos' : 'Sin datos'
              }
            />
            <Bar dataKey="average" name="Promedio" fill="#2563eb" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState message="No hay datos de primera respuesta para las marcas seleccionadas." />
      )}
    </ChartCard>
  )
}
