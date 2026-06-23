import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { DataQualityRuleRow } from '../../types/dashboard'
import { ChartCard } from './ChartCard'
import { EmptyState } from '../ui/EmptyState'

interface DataQualityChartProps {
  data: DataQualityRuleRow[]
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  warning: '#f59e0b',
  info: '#64748b',
}

export function DataQualityChart({ data }: DataQualityChartProps) {
  const hasData = data.some((row) => row.count > 0)

  return (
    <ChartCard
      title="Calidad de datos del CRM"
      description="Hallazgos por regla de validación"
      dataStatus={hasData ? 'available' : 'partial'}
    >
      {hasData ? (
        <ResponsiveContainer width="100%" height={320}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 8, right: 8, left: 8, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis type="number" tick={{ fill: '#64748b', fontSize: 12 }} />
            <YAxis
              type="category"
              dataKey="label"
              width={180}
              tick={{ fill: '#64748b', fontSize: 11 }}
            />
            <Tooltip />
            <Bar dataKey="count" name="Registros" radius={[0, 4, 4, 0]}>
              {data.map((row) => (
                <Cell
                  key={row.rule_code}
                  fill={SEVERITY_COLORS[row.severity] ?? SEVERITY_COLORS.info}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState message="No hay hallazgos de calidad registrados." />
      )}
    </ChartCard>
  )
}
