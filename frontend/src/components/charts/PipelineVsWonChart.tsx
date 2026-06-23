import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { TrendPoint } from '@/types/dashboard'
import { weekAxisInterval } from '../../lib/chartTicks'
import { formatCopAbbrev } from '../../lib/format'
import { ChartCard } from './ChartCard'
import { EmptyState } from '../ui/EmptyState'

interface PipelineVsWonChartProps {
  data: TrendPoint[]
}

export function PipelineVsWonChart({ data }: PipelineVsWonChartProps) {
  const hasData = data.some(
    (point) => (point.pipeline_created_amount ?? 0) > 0 || (point.won_amount ?? 0) > 0,
  )

  return (
    <ChartCard
      title="Pipeline generado vs ventas ganadas"
      description="Historial completo por semana (COP)"
      dataStatus="available"
    >
      {hasData ? (
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="week_label"
              tick={{ fill: '#64748b', fontSize: 12 }}
              interval={weekAxisInterval(data.length)}
            />
            <YAxis
              tick={{ fill: '#64748b', fontSize: 12 }}
              tickFormatter={(value: number) => formatCopAbbrev(value)}
            />
            <Tooltip
              formatter={(value) =>
                typeof value === 'number' ? formatCopAbbrev(value) : 'Sin datos'
              }
            />
            <Legend />
            <Area
              type="monotone"
              dataKey="pipeline_created_amount"
              name="Pipeline"
              fill="#dbeafe"
              stroke="#2563eb"
            />
            <Line
              type="monotone"
              dataKey="won_amount"
              name="Ganado"
              stroke="#059669"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState message="No hay montos de pipeline o ventas en el periodo." />
      )}
    </ChartCard>
  )
}
