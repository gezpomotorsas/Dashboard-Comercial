import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type {
  ActivityOutcomesData,
  BrandZoneRow,
  DealAnalyticsFilterValues,
  DealGroupRow,
  InactivityDistributionData,
  OwnerAnalyticsRow,
} from '@/types/dealAnalytics'
import {
  useActivityOutcomes,
  useBrandsZones,
  useDealAnalyticsFilters,
  useDealExplorer,
  useDealFunnel,
  useDealOwners,
  useDealSummary,
  useDealsByBrand,
  useDealsByStage,
  useDealsByZone,
  useInactivityDistribution,
} from '@/hooks/useDealAnalytics'
import { ChartCard } from '@/components/charts/ChartCard'
import { MetricDataTable } from '@/components/deal-analytics/MetricDataTable'
import { ErrorState } from '@/components/ui/ErrorState'
import {
  ADVISORS_COMPARE_COLUMNS,
  BRAND_ZONE_COLUMNS,
  EXPLORER_COLUMNS,
  FUNNEL_COLUMNS,
} from '@/lib/metricTooltips'
import { formatCop, formatPercent } from '@/lib/format'

type View = 'resumen' | 'marcas' | 'embudo' | 'gestion' | 'asesores' | 'explorador'

const VIEWS: { id: View; label: string }[] = [
  { id: 'resumen', label: 'Resumen' },
  { id: 'marcas', label: 'Marcas y zonas' },
  { id: 'embudo', label: 'Embudo' },
  { id: 'gestion', label: 'Gestión' },
  { id: 'asesores', label: 'Asesores' },
  { id: 'explorador', label: 'Negocios' },
]

const STATUS_COLORS: Record<string, string> = {
  open: '#2563eb',
  won: '#16a34a',
  lost: '#dc2626',
  unknown: '#94a3b8',
}

const UNATTENDED_LABELS: Record<string, string> = {
  no_recent_activity: 'Sin actividad 30d',
  no_recent_effective_contact: 'Sin contacto efectivo 30d',
  overdue_tasks: 'Tareas vencidas',
  no_future_task: 'Sin próxima tarea',
  multiple_reasons: 'Múltiples señales',
}

export function DealAnalyticsPage() {
  const [view, setView] = useState<View>('resumen')
  const [portfolioOpenOnly, setPortfolioOpenOnly] = useState(true)
  const [filters, setFilters] = useState<DealAnalyticsFilterValues>({ status: 'open' })

  const activeFilters = useMemo(
    () => ({
      ...filters,
      status: portfolioOpenOnly ? 'open' : filters.status,
    }),
    [filters, portfolioOpenOnly],
  )

  const filterOptions = useDealAnalyticsFilters()
  const summary = useDealSummary(activeFilters)
  const byStage = useDealsByStage(activeFilters)
  const byBrand = useDealsByBrand(activeFilters)
  const byZone = useDealsByZone(activeFilters)
  const brandsZones = useBrandsZones(activeFilters)
  const owners = useDealOwners(activeFilters)
  const explorer = useDealExplorer({
    ...activeFilters,
    limit: 100,
    offset: 0,
    sort_by: 'days_since_last_activity',
    sort_dir: 'desc',
  })
  const funnel = useDealFunnel(activeFilters)
  const activity = useActivityOutcomes(activeFilters)
  const inactivity = useInactivityDistribution(activeFilters)

  const showSummaryLoading = summary.isPending && !summary.data

  const activityData = activity.data?.data as ActivityOutcomesData | undefined
  const inactivityData = inactivity.data?.data as InactivityDistributionData | undefined
  const summaryData = summary.data?.data

  const cards = useMemo(() => {
    if (!summaryData) return []
    const open = summaryData.open_deals
    return [
      { label: 'Negocios en población', value: summaryData.total_deals.toLocaleString('es-CO') },
      { label: 'Cartera abierta', value: open.toLocaleString('es-CO') },
      {
        label: 'Pipeline abierto',
        value: formatCop(summaryData.open_pipeline_amount),
        hint: 'Solo negocios abiertos',
      },
      {
        label: 'Gestionados 30d',
        value:
          summaryData.open_managed_30d_rate != null
            ? `${summaryData.open_managed_30d} (${formatPercent(summaryData.open_managed_30d_rate)})`
            : '—',
        hint: 'Abiertos con actividad en ventana sincronizada',
      },
      {
        label: 'Contacto efectivo 30d',
        value:
          summaryData.open_effective_contact_30d_rate != null
            ? `${summaryData.open_effective_contact_30d} (${formatPercent(summaryData.open_effective_contact_30d_rate)})`
            : '—',
      },
      { label: 'Desatendidos (abiertos)', value: summaryData.unattended_open_deals.toLocaleString('es-CO') },
      { label: 'Estancados', value: summaryData.stale_deals.toLocaleString('es-CO') },
      { label: 'Con tareas vencidas', value: summaryData.deals_with_overdue_tasks.toLocaleString('es-CO') },
      { label: 'Sin propietario', value: summaryData.deals_without_owner.toLocaleString('es-CO') },
      { label: 'Ganados (hist.)', value: summaryData.won_deals.toLocaleString('es-CO') },
      { label: 'Valor ganado (hist.)', value: formatCop(summaryData.won_amount) },
    ]
  }, [summaryData])

  const drillChips = [
    filters.brand_value && {
      key: 'brand',
      label: filterOptions.data?.brands.find((b) => b.value === filters.brand_value)?.label ?? filters.brand_value,
      onClear: () => setFilters((p) => ({ ...p, brand_value: undefined })),
    },
    filters.zone_value && {
      key: 'zone',
      label: filterOptions.data?.zones.find((z) => z.value === filters.zone_value)?.label ?? filters.zone_value,
      onClear: () => setFilters((p) => ({ ...p, zone_value: undefined })),
    },
    filters.pipeline_id && {
      key: 'pipeline',
      label:
        filterOptions.data?.pipelines.find((p) => p.value === filters.pipeline_id)?.label ??
        filters.pipeline_id,
      onClear: () => setFilters((p) => ({ ...p, pipeline_id: undefined })),
    },
    filters.stage_id && {
      key: 'stage',
      label: filterOptions.data?.stages.find((s) => s.value === filters.stage_id)?.label ?? filters.stage_id,
      onClear: () => setFilters((p) => ({ ...p, stage_id: undefined })),
    },
    filters.owner_id && {
      key: 'owner',
      label: filterOptions.data?.owners.find((o) => o.value === filters.owner_id)?.label ?? filters.owner_id,
      onClear: () => setFilters((p) => ({ ...p, owner_id: undefined })),
    },
  ].filter(Boolean) as Array<{ key: string; label: string; onClear: () => void }>

  const primaryError = summary.error ?? filterOptions.error

  if (primaryError) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <ErrorState
          title="No se pudo cargar la analítica"
          message={primaryError instanceof Error ? primaryError.message : 'Error de conexión con la API'}
          onRetry={() => {
            void filterOptions.refetch()
            void summary.refetch()
          }}
        />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white px-6 py-5">
        <p className="text-sm uppercase tracking-wide text-blue-600">Gezpomotor · Cartera comercial</p>
        <h1 className="text-2xl font-semibold">Analítica centrada en negocios</h1>
        <p className="text-slate-600">
          Empresa → Marca → Zona → Pipeline → Etapa → Asesor → Negocio
        </p>
        {summary.data && (
          <p className="mt-2 text-sm text-slate-500">
            Población analizada: {summary.data.population.included_deals.toLocaleString('es-CO')} de{' '}
            {summary.data.population.total_deals.toLocaleString('es-CO')} negocios ·{' '}
            {summaryData?.activity_coverage_note ??
              `Actividades: ${summary.data.data_quality.activity_coverage ?? 'parcial'}`}
          </p>
        )}
      </header>

      <div className="border-b bg-white px-6 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 rounded-full border px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={portfolioOpenOnly}
              onChange={(e) => {
                setPortfolioOpenOnly(e.target.checked)
                if (e.target.checked) {
                  setFilters((p) => ({ ...p, status: 'open' }))
                }
              }}
            />
            Enfoque cartera abierta
          </label>
          {!portfolioOpenOnly && (
            <select
              className="rounded border px-3 py-2 text-sm"
              value={filters.status ?? 'all'}
              onChange={(e) =>
                setFilters((prev) => ({
                  ...prev,
                  status: e.target.value === 'all' ? undefined : e.target.value,
                }))
              }
            >
              <option value="all">Todos los estados</option>
              {filterOptions.data?.statuses.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          )}
          <FilterSelect
            label="Pipeline"
            value={filters.pipeline_id}
            options={filterOptions.data?.pipelines ?? []}
            onChange={(v) => setFilters((p) => ({ ...p, pipeline_id: v }))}
          />
          <FilterSelect
            label="Marca"
            value={filters.brand_value}
            options={filterOptions.data?.brands ?? []}
            onChange={(v) => setFilters((p) => ({ ...p, brand_value: v }))}
          />
          <FilterSelect
            label="Zona"
            value={filters.zone_value}
            options={filterOptions.data?.zones ?? []}
            onChange={(v) => setFilters((p) => ({ ...p, zone_value: v }))}
          />
          <FilterSelect
            label="Etapa"
            value={filters.stage_id}
            options={filterOptions.data?.stages ?? []}
            onChange={(v) => setFilters((p) => ({ ...p, stage_id: v }))}
          />
          <FilterSelect
            label="Asesor"
            value={filters.owner_id}
            options={filterOptions.data?.owners ?? []}
            onChange={(v) => setFilters((p) => ({ ...p, owner_id: v }))}
          />
          <button
            type="button"
            className="rounded border px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            onClick={() =>
              setFilters(portfolioOpenOnly ? { status: 'open' } : {})
            }
          >
            Limpiar filtros
          </button>
        </div>

        {drillChips.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {drillChips.map((chip) => (
              <button
                key={chip.key}
                type="button"
                onClick={chip.onClear}
                className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-800"
              >
                {chip.label} ×
              </button>
            ))}
          </div>
        )}

        <nav className="mt-4 flex flex-wrap gap-2">
          {VIEWS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setView(item.id)}
              className={`rounded-full px-4 py-2 text-sm ${
                view === item.id ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700'
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </div>

      <main className="space-y-6 p-6">
        <div className={view === 'resumen' ? undefined : 'hidden'}>
          {showSummaryLoading ? (
            <LoadingBlock />
          ) : (
            <>
              <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {cards.map((card) => (
                  <article key={card.label} className="rounded-xl border bg-white p-4 shadow-sm">
                    <p className="text-sm text-slate-500">{card.label}</p>
                    <p className="mt-2 text-2xl font-semibold">{card.value}</p>
                    {'hint' in card && card.hint ? (
                      <p className="mt-1 text-xs text-slate-400">{card.hint}</p>
                    ) : null}
                  </article>
                ))}
              </section>
              <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard title="Estado de la cartera" description="Distribución de la población filtrada">
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={summaryData?.status_distribution ?? []}
                          dataKey="count"
                          nameKey="label"
                          innerRadius={50}
                          outerRadius={90}
                        >
                          {(summaryData?.status_distribution ?? []).map((entry) => (
                            <Cell key={entry.status} fill={STATUS_COLORS[entry.status] ?? '#64748b'} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </ChartCard>
                <GroupChart
                  title="Negocios por marca"
                  description="Clic en barra para filtrar"
                  data={byBrand.data?.data ?? []}
                  onSelect={(key) => setFilters((p) => ({ ...p, brand_value: key }))}
                />
              </div>
              <div className="grid gap-6 lg:grid-cols-2">
                <GroupChart
                  title="Negocios por zona"
                  description="Clic en barra para filtrar"
                  data={byZone.data?.data ?? []}
                  horizontal
                  onSelect={(key) => setFilters((p) => ({ ...p, zone_value: key }))}
                />
                <GroupChart
                  title="Negocios por etapa"
                  data={byStage.data?.data ?? []}
                  onSelect={(key) => setFilters((p) => ({ ...p, stage_id: key }))}
                />
              </div>
            </>
          )}
        </div>

        <div className={view === 'marcas' ? undefined : 'hidden'}>
          <MetricDataTable
            loading={brandsZones.isPending && !brandsZones.data}
            title="Comparativa marca × zona"
            description="Pasa el mouse sobre cada columna para ver qué mide."
            columns={BRAND_ZONE_COLUMNS}
            rows={(brandsZones.data?.data ?? []).map((row: BrandZoneRow) => [
              row.brand_label,
              row.zone_label,
              row.total_deals,
              row.open_deals,
              formatCop(row.open_pipeline_amount),
              row.managed_30d_rate != null ? formatPercent(row.managed_30d_rate) : '—',
              row.effective_contact_30d_rate != null ? formatPercent(row.effective_contact_30d_rate) : '—',
              row.unattended_open_deals,
              row.deals_with_overdue_tasks,
              row.close_rate != null ? formatPercent(row.close_rate) : '—',
            ])}
          />
        </div>

        <div className={view === 'embudo' ? undefined : 'hidden'}>
          <MetricDataTable
            loading={funnel.isPending && !funnel.data}
            title="Embudo por etapa (etapa actual)"
            description="Pasa el mouse sobre cada columna para ver qué mide."
            columns={FUNNEL_COLUMNS}
            rows={(
              (funnel.data?.data as Array<Record<string, unknown>> | undefined) ?? []
            ).map((row) => [
              String(row.stage_label),
              Number(row.count),
              Number(row.open_count),
              Number(row.won_count),
              Number(row.lost_count),
              Number(row.stale_count),
            ])}
          />
        </div>

        <div className={view === 'gestion' ? undefined : 'hidden'}>
          <div className="grid gap-6 lg:grid-cols-2">
            <MetricList
              title="Cobertura de gestión (ventana sincronizada)"
              items={[
                ['Gestionados 7d', activityData?.deals_managed_last_7d],
                ['Gestionados 30d', activityData?.deals_managed_last_30d],
                ['Gestionados 60d', activityData?.deals_managed_last_60d],
                ['Sin actividad registrada', activityData?.deals_without_activity],
                ['Sin contacto efectivo', activityData?.deals_without_effective_contact],
              ]}
            />
            <MetricList
              title="Días sin actividad"
              items={[
                ['Sin actividad 7d', inactivityData?.deals_without_activity_7d],
                ['Sin actividad 30d', inactivityData?.deals_without_activity_30d],
                ['Sin actividad 60d', inactivityData?.deals_without_activity_60d],
                ['Sin actividad en ventana', inactivityData?.deals_without_any_activity],
              ]}
            />
          </div>
        </div>

        <div className={view === 'asesores' ? undefined : 'hidden'}>
          <MetricDataTable
            loading={owners.isPending && !owners.data}
            title="Comparativa de asesores — disciplina y efectividad"
            description="Pasa el mouse sobre cada columna para ver qué mide."
            columns={ADVISORS_COMPARE_COLUMNS}
            rows={(owners.data?.data ?? []).map((row: OwnerAnalyticsRow) => [
              row.owner_name ?? 'Sin asignar',
              row.assigned_deals,
              row.open_deals,
              row.managed_30d_rate != null ? formatPercent(row.managed_30d_rate) : '—',
              row.effective_contact_30d_rate != null ? formatPercent(row.effective_contact_30d_rate) : '—',
              row.no_activity_30d_open,
              row.overdue_tasks_deals,
              row.unattended_open_deals,
              row.discipline_score ?? '—',
              row.effectiveness_score ?? '—',
              row.management_status,
              row.close_rate != null ? formatPercent(row.close_rate) : '—',
            ])}
          />
        </div>

        <div className={view === 'explorador' ? undefined : 'hidden'}>
          <MetricDataTable
            loading={explorer.isPending && !explorer.data}
            title="Cola de acción — negocios prioritarios"
            description="Pasa el mouse sobre cada columna para ver qué mide."
            columns={EXPLORER_COLUMNS}
            rows={(explorer.data?.data.items ?? []).map((row) => [
              row.deal_name ?? row.deal_id,
              row.brand_label ?? '—',
              row.zone_label ?? '—',
              row.stage_label ?? '—',
              row.owner_name ?? '—',
              row.amount != null ? formatCop(row.amount) : '—',
              row.days_since_last_activity ?? '—',
              row.days_since_effective_contact ?? '—',
              row.overdue_task_count ?? 0,
              row.is_unattended
                ? UNATTENDED_LABELS[row.unattended_reason ?? ''] ?? row.alert_reason ?? 'Revisar'
                : row.is_stale
                  ? 'Estancado'
                  : '—',
            ])}
          />
        </div>
      </main>
    </div>
  )
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value?: string
  options: Array<{ value: string; label: string }>
  onChange: (value: string | undefined) => void
}) {
  return (
    <select
      className="rounded border px-3 py-2 text-sm"
      value={value ?? 'all'}
      onChange={(e) => onChange(e.target.value === 'all' ? undefined : e.target.value)}
      aria-label={label}
    >
      <option value="all">Todas — {label}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

function GroupChart({
  title,
  description,
  data,
  horizontal,
  onSelect,
}: {
  title: string
  description?: string
  data: DealGroupRow[]
  horizontal?: boolean
  onSelect?: (key: string) => void
}) {
  const chartData = data.map((d) => ({ ...d, name: d.label }))
  return (
    <ChartCard title={title} description={description}>
      <div className={horizontal ? 'h-80' : 'h-72'}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout={horizontal ? 'vertical' : 'horizontal'}
            margin={horizontal ? { left: 80 } : undefined}
          >
            <CartesianGrid strokeDasharray="3 3" />
            {horizontal ? (
              <>
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="name" width={75} tick={{ fontSize: 11 }} />
              </>
            ) : (
              <>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
              </>
            )}
            <Tooltip />
            <Bar
              dataKey="count"
              fill="#2563eb"
              radius={4}
              cursor={onSelect ? 'pointer' : undefined}
              onClick={(payload) => {
                if (onSelect && payload?.key) onSelect(String(payload.key))
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}

function MetricList({ title, items }: { title: string; items: Array<[string, unknown]> }) {
  return (
    <section className="rounded-xl border bg-white p-4 shadow-sm">
      <h2 className="mb-4 text-lg font-medium">{title}</h2>
      <dl className="space-y-3">
        {items.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between border-b pb-2">
            <dt className="text-slate-600">{label}</dt>
            <dd className="font-medium">{value == null ? '—' : String(value)}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function LoadingBlock() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="h-24 animate-pulse rounded-xl border bg-white" />
      ))}
    </div>
  )
}
