import { useMemo, useState } from 'react'
import { format, parseISO } from 'date-fns'
import { es } from 'date-fns/locale'
import {
  DashboardFilters,
  type DashboardFilterValues,
} from './DashboardFilters'
import { KpiCardGrid } from './KpiCardGrid'
import { DashboardChartsGrid } from '../charts/DashboardChartsGrid'
import { useDashboardFilters } from '../../hooks/useDashboardFilters'
import { useDashboardWeekly } from '../../hooks/useDashboardWeekly'
import { DashboardSkeleton, ChartSkeleton } from '../ui/DashboardSkeleton'
import { ErrorState } from '../ui/ErrorState'

const EMPTY_FILTERS: DashboardFilterValues = {
  week_start: '',
  brand: 'all',
  owner_id: 'all',
  pipeline_id: 'all',
}

export function DashboardPage() {
  const filtersQuery = useDashboardFilters()
  const [filterValues, setFilterValues] = useState<DashboardFilterValues>(EMPTY_FILTERS)

  const effectiveFilters = useMemo(() => {
    if (!filtersQuery.data) {
      return filterValues
    }
    if (filterValues.week_start) {
      return filterValues
    }
    return {
      ...filterValues,
      week_start: filtersQuery.data.weeks[0]?.value ?? '',
    }
  }, [filterValues, filtersQuery.data])

  const weeklyParams = useMemo(() => {
    if (!effectiveFilters.week_start) {
      return null
    }

    return {
      week_start: effectiveFilters.week_start,
      brand: effectiveFilters.brand,
      owner_id: effectiveFilters.owner_id === 'all' ? undefined : effectiveFilters.owner_id,
      pipeline_id:
        effectiveFilters.pipeline_id === 'all' ? undefined : effectiveFilters.pipeline_id,
    }
  }, [effectiveFilters])

  const weeklyQuery = useDashboardWeekly(weeklyParams)

  const weekLabel = useMemo(() => {
    if (!weeklyQuery.data?.filters.week_start) {
      return null
    }
    try {
      const start = parseISO(weeklyQuery.data.filters.week_start)
      const end = parseISO(weeklyQuery.data.filters.week_end)
      return `${format(start, "d MMM", { locale: es })} – ${format(end, "d MMM yyyy", { locale: es })}`
    } catch {
      return weeklyQuery.data.filters.week_start
    }
  }, [weeklyQuery.data])

  if (filtersQuery.isLoading && !filtersQuery.data) {
    return <DashboardSkeleton />
  }

  if (filtersQuery.isError) {
    return (
      <ErrorState
        title="No se pudieron cargar los filtros"
        message={filtersQuery.error?.message ?? 'Error desconocido'}
        onRetry={() => filtersQuery.refetch()}
      />
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-blue-600">
            Dashboard gerencial
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Resumen semanal comercial
          </h1>
          {weekLabel ? (
            <p className="text-sm text-slate-500">Semana del {weekLabel}</p>
          ) : null}
        </div>
        {weeklyQuery.data?.metadata ? (
          <p
            className="max-w-sm text-xs text-slate-500"
            title="Ventana de sincronización de actividades HubSpot"
          >
            Actividades: historial sincronizado en Supabase
            {!weeklyQuery.data.metadata.email_tracking_enabled && ' · Emails deshabilitados'}
            {weeklyQuery.data.metadata.owner_scope_active &&
              weeklyQuery.data.metadata.owner_scope_note && (
                <>
                  <br />
                  <span title={weeklyQuery.data.metadata.owner_scope_note}>
                    Vista por asesor: incluye gestión comercial vía actividades
                  </span>
                </>
              )}
          </p>
        ) : null}
      </header>

      <DashboardFilters
        filters={filtersQuery.data!}
        values={effectiveFilters}
        onChange={setFilterValues}
      />

      {weeklyQuery.isError ? (
        <ErrorState
          message={weeklyQuery.error?.message ?? 'No se pudo cargar el dashboard semanal.'}
          onRetry={() => weeklyQuery.refetch()}
        />
      ) : null}

      <KpiCardGrid
        cards={weeklyQuery.data?.cards}
        isLoading={weeklyQuery.isLoading && !weeklyQuery.data}
      />

      {weeklyQuery.isLoading && !weeklyQuery.data ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <ChartSkeleton key={index} />
          ))}
        </div>
      ) : null}

      {weeklyQuery.data ? (
        <>
          <DashboardChartsGrid
            charts={weeklyQuery.data.charts}
            activityWindowDays={weeklyQuery.data.metadata.activity_window_days}
            ownerFilterActive={weeklyQuery.data.metadata.owner_scope_active ?? false}
          />
          <footer className="text-center text-xs text-slate-400">
            Actualizado{' '}
            {format(parseISO(weeklyQuery.data.metadata.generated_at), 'PPpp', { locale: es })}
            {' · '}
            Zona {weeklyQuery.data.metadata.timezone}
          </footer>
        </>
      ) : null}
    </div>
  )
}
