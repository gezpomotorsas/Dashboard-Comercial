import {
  Bar,
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
import { ChartCard } from './ChartCard'
import { EmptyState } from '../ui/EmptyState'

interface LeadsDealsTrendChartProps {
  data: TrendPoint[]
}

export function LeadsDealsTrendChart({ data }: LeadsDealsTrendChartProps) {
  const hasData = data.some(
    (point) => (point.leads_created ?? 0) > 0 || (point.deals_created ?? 0) > 0,
  )

  return (
    <ChartCard
      title="Tendencia de leads y negocios"
      description="Historial completo por semana"
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
            <YAxis tick={{ fill: '#64748b', fontSize: 12 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="leads_created" name="Leads" fill="#2563eb" radius={[4, 4, 0, 0]} />
            <Line
              type="monotone"
              dataKey="deals_created"
              name="Negocios"
              stroke="#0ea5e9"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState message="No hay actividad de captación en el periodo seleccionado." />
      )}
    </ChartCard>
  )
}
