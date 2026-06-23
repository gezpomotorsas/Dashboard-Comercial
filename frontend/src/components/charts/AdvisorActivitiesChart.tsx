import { useMemo, useState } from 'react'
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
import type { AdvisorActivityRow } from '../../types/dashboard'
import { ChartCard } from './ChartCard'
import { EmptyState } from '../ui/EmptyState'
import { Button } from '../ui/button'

type ActivityMode = 'effective' | 'internal'

const PAGE_SIZE = 10

interface AdvisorActivitiesChartProps {
  data: AdvisorActivityRow[]
  activityWindowDays?: number
  ownerFilterActive?: boolean
}

export function AdvisorActivitiesChart({
  data,
  activityWindowDays = 60,
  ownerFilterActive = false,
}: AdvisorActivitiesChartProps) {
  const [mode, setMode] = useState<ActivityMode>('effective')
  const [visible, setVisible] = useState(PAGE_SIZE)

  const sorted = useMemo(
    () =>
      [...data].sort((a, b) => {
        const totalA = mode === 'effective' ? a.total_effective : a.tasks + a.notes
        const totalB = mode === 'effective' ? b.total_effective : b.tasks + b.notes
        return totalB - totalA
      }),
    [data, mode],
  )

  const chartData = sorted.slice(0, visible)
  const hasData = sorted.length > 0

  return (
    <ChartCard
      title="Gestión comercial por asesor"
      description={
        ownerFilterActive
          ? `Últimos ${activityWindowDays} días hasta el fin de la semana seleccionada`
          : `Semana seleccionada · sincronización en ventana de ${activityWindowDays} días`
      }
      dataStatus="available"
      className="xl:col-span-2"
      action={
        <div className="flex gap-2">
          <Button
            variant={mode === 'effective' ? 'default' : 'outline'}
            onClick={() => setMode('effective')}
          >
            Contacto efectivo
          </Button>
          <Button
            variant={mode === 'internal' ? 'default' : 'outline'}
            onClick={() => setMode('internal')}
          >
            Gestión interna
          </Button>
        </div>
      }
    >
      {hasData ? (
        <>
          <ResponsiveContainer width="100%" height={360}>
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 8, right: 8, left: 8, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
              <XAxis type="number" tick={{ fill: '#64748b', fontSize: 12 }} allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="owner_name"
                width={120}
                tick={{ fill: '#64748b', fontSize: 11 }}
              />
              <Tooltip />
              <Legend />
              {mode === 'effective' ? (
                <>
                  <Bar dataKey="calls" name="Llamadas" stackId="a" fill="#2563eb" />
                  <Bar dataKey="communications" name="Comunicaciones" stackId="a" fill="#14b8a6" />
                  <Bar dataKey="completed_meetings" name="Reuniones" stackId="a" fill="#8b5cf6" />
                </>
              ) : (
                <>
                  <Bar dataKey="tasks" name="Tareas" stackId="b" fill="#f59e0b" />
                  <Bar dataKey="notes" name="Notas" stackId="b" fill="#64748b" />
                </>
              )}
            </BarChart>
          </ResponsiveContainer>
          {sorted.length > visible ? (
            <div className="mt-2 text-center">
              <Button variant="ghost" onClick={() => setVisible((v) => v + PAGE_SIZE)}>
                Ver más asesores ({sorted.length - visible} restantes)
              </Button>
            </div>
          ) : null}
        </>
      ) : (
        <EmptyState message="No hay actividades registradas para los asesores en esta semana." />
      )}
    </ChartCard>
  )
}
