import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { CloseRateChart as CloseRateChartData } from '../../types/dashboard'
import { ChartCard } from './ChartCard'
import { EmptyState } from '../ui/EmptyState'

interface CloseRateChartProps {
  data: CloseRateChartData
}

const COLORS = ['#10b981', '#f43f5e']

export function CloseRateChart({ data }: CloseRateChartProps) {
  const unavailable = data.data_status === 'unavailable' || data.close_rate == null
  const pieData = [
    { name: 'Ganados', value: data.won_deals },
    { name: 'Perdidos', value: data.lost_deals },
  ]
  const hasDeals = data.won_deals + data.lost_deals > 0

  return (
    <ChartCard
      title="Tasa de cierre"
      description={
        unavailable
          ? 'Sin datos de cierre en la semana'
          : `${data.close_rate?.toFixed(1)}% de cierre`
      }
      dataStatus={data.data_status}
    >
      {unavailable || !hasDeals ? (
        <EmptyState message="No hay negocios cerrados en la semana seleccionada." />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Pie
              data={pieData}
              dataKey="value"
              nameKey="name"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={3}
            >
              {pieData.map((_, index) => (
                <Cell key={index} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}
