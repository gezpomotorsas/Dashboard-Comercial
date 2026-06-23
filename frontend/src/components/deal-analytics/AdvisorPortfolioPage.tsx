import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ArrowLeft } from 'lucide-react'
import { ChartCard } from '@/components/charts/ChartCard'
import { ContactMethodologySection } from '@/components/deal-analytics/ContactMethodologySection'
import { WonSalesSummaryStrip } from '@/components/deal-analytics/WonSalesSummaryStrip'
import { AdvisorTaskTable } from '@/components/deal-analytics/AdvisorTaskTable'
import { ErrorState } from '@/components/ui/ErrorState'
import { SlowLoadNotice } from '@/components/ui/SlowLoadNotice'
import { useAdvisorPortfolio } from '@/hooks/useAdvisorPortfolio'
import { useBrandOperating, type OperatingBrand } from '@/hooks/useBrandOperating'
import { mergeWeeklyCounts } from '@/lib/weeklyChartMerge'
import { staleChartSeriesLabel } from '@/lib/brandStale'
import { formatPercent } from '@/lib/format'
import { weekAxisInterval } from '@/lib/chartTicks'
import type { AdvisorPortfolioTask } from '@/types/dealAnalytics'

const BRANDS: { id: OperatingBrand; label: string }[] = [
  { id: 'voyah', label: 'Voyah' },
  { id: 'mhero', label: 'MHero' },
  { id: 'shacman', label: 'Shacman' },
]

type TaskFilter = 'all' | 'pending' | 'overdue' | 'completed_late' | 'completed'
type TaskTimeFilter = 'all' | 'due_7d' | 'due_30d' | 'due_past' | 'created_7d' | 'created_30d' | 'custom_due'

const TASK_TIME_FILTERS: { id: TaskTimeFilter; label: string }[] = [
  { id: 'all', label: 'Cualquier fecha' },
  { id: 'due_7d', label: 'Vence 7d' },
  { id: 'due_30d', label: 'Vence 30d' },
  { id: 'due_past', label: 'Ya venció' },
  { id: 'created_7d', label: 'Creada 7d' },
  { id: 'created_30d', label: 'Creada 30d' },
  { id: 'custom_due', label: 'Rango vencimiento' },
]

const TASK_FILTERS: { id: TaskFilter; label: string }[] = [
  { id: 'all', label: 'Todas' },
  { id: 'pending', label: 'Pendientes' },
  { id: 'overdue', label: 'Vencidas' },
  { id: 'completed_late', label: 'Completadas atrasadas' },
  { id: 'completed', label: 'Completadas' },
]

function taskFlag(value: unknown): boolean {
  return value === true || value === 'true'
}

function parseTaskDate(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? null : date
}

function startOfLocalDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function filterTasksByTime(
  tasks: AdvisorPortfolioTask[],
  timeFilter: TaskTimeFilter,
  dueFrom: string,
  dueTo: string,
): AdvisorPortfolioTask[] {
  if (timeFilter === 'all') return tasks

  const now = startOfLocalDay(new Date())
  const inDays = (days: number) => {
    const end = new Date(now)
    end.setDate(end.getDate() + days)
    return end
  }
  const daysAgo = (days: number) => {
    const start = new Date(now)
    start.setDate(start.getDate() - days)
    return start
  }

  return tasks.filter((task) => {
    const due = parseTaskDate(task.due_at)
    const created = parseTaskDate(task.created_at)

    switch (timeFilter) {
      case 'due_7d':
        return due != null && due >= now && due <= inDays(7)
      case 'due_30d':
        return due != null && due >= now && due <= inDays(30)
      case 'due_past':
        return due != null && due < now && !taskFlag(task.is_completed)
      case 'created_7d':
        return created != null && created >= daysAgo(7)
      case 'created_30d':
        return created != null && created >= daysAgo(30)
      case 'custom_due': {
        if (!due) return false
        const from = dueFrom ? startOfLocalDay(new Date(`${dueFrom}T00:00:00`)) : null
        const to = dueTo ? startOfLocalDay(new Date(`${dueTo}T23:59:59`)) : null
        if (from && due < from) return false
        if (to && due > to) return false
        return Boolean(from || to)
      }
      default:
        return true
    }
  })
}

function filterTasks(tasks: AdvisorPortfolioTask[], filter: TaskFilter): AdvisorPortfolioTask[] {
  switch (filter) {
    case 'overdue':
      return tasks.filter((t) => taskFlag(t.is_overdue))
    case 'completed_late':
      return tasks.filter((t) => taskFlag(t.is_completed_late))
    case 'completed':
      return tasks.filter((t) => taskFlag(t.is_completed))
    case 'pending':
      return tasks.filter((t) => !taskFlag(t.is_completed))
    default:
      return tasks
  }
}

function isOperatingBrand(value: string | undefined): value is OperatingBrand {
  return value === 'voyah' || value === 'mhero' || value === 'shacman'
}

function advisorRouteId(ownerId: string | null): string {
  return ownerId ?? 'unassigned'
}

export function AdvisorPortfolioPage() {
  const navigate = useNavigate()
  const params = useParams<{ brand?: string; ownerId?: string }>()
  const brand: OperatingBrand = isOperatingBrand(params.brand) ? params.brand : 'voyah'
  const ownerId = params.ownerId

  const operatingQuery = useBrandOperating(brand)
  const portfolioQuery = useAdvisorPortfolio(brand, ownerId)
  const [compareOwnerId, setCompareOwnerId] = useState<string>('')
  const compareQuery = useAdvisorPortfolio(brand, compareOwnerId || undefined)
  const [taskFilter, setTaskFilter] = useState<TaskFilter>('all')
  const [taskTimeFilter, setTaskTimeFilter] = useState<TaskTimeFilter>('all')
  const [taskDueFrom, setTaskDueFrom] = useState('')
  const [taskDueTo, setTaskDueTo] = useState('')

  const advisors = operatingQuery.data?.data.advisors ?? []
  const portfolio = portfolioQuery.data?.data
  const comparePortfolio = compareQuery.data?.data

  const weeklyCreatedChart = useMemo(() => {
    if (!portfolio) return []
    const created = portfolio.charts.weekly_created ?? []
    const primaryName = portfolio.advisor.owner_name
    if (!comparePortfolio) {
      return created.map((row) => ({
        week_start: row.week_start,
        [primaryName]: row.deals_created,
      }))
    }
    return mergeWeeklyCounts(
      created,
      comparePortfolio.charts.weekly_created ?? [],
      'deals_created',
      'deals_created',
      primaryName,
      comparePortfolio.advisor.owner_name,
    )
  }, [portfolio, comparePortfolio])

  const statusFilteredTasks = useMemo(
    () => filterTasks(portfolio?.tasks ?? [], taskFilter),
    [portfolio?.tasks, taskFilter],
  )

  const filteredTasks = useMemo(
    () => filterTasksByTime(statusFilteredTasks, taskTimeFilter, taskDueFrom, taskDueTo),
    [statusFilteredTasks, taskTimeFilter, taskDueFrom, taskDueTo],
  )

  const taskCounts = portfolio?.task_counts
  const taskFilterCounts: Record<TaskFilter, number> = {
    all: taskCounts?.total ?? filteredTasks.length,
    pending: taskCounts?.pending ?? filterTasks(portfolio?.tasks ?? [], 'pending').length,
    overdue: taskCounts?.overdue ?? filterTasks(portfolio?.tasks ?? [], 'overdue').length,
    completed_late:
      taskCounts?.completed_late ?? filterTasks(portfolio?.tasks ?? [], 'completed_late').length,
    completed: taskCounts?.completed ?? filterTasks(portfolio?.tasks ?? [], 'completed').length,
  }

  const wonSales = useMemo(() => {
    if (portfolio?.won_sales) return portfolio.won_sales
    const advisor = advisors.find((row) => advisorRouteId(row.owner_id) === ownerId)
    return advisor?.won_sales
  }, [portfolio?.won_sales, advisors, ownerId])

  const staleSeriesLabel = staleChartSeriesLabel(brand)

  function selectBrand(nextBrand: OperatingBrand) {
    if (ownerId) navigate(`/asesor/${nextBrand}/${ownerId}`)
    else navigate(`/asesor/${nextBrand}`)
  }

  function selectAdvisor(id: string) {
    setCompareOwnerId('')
    navigate(`/asesor/${brand}/${id}`)
  }

  if (operatingQuery.error) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <ErrorState
          title="No se pudo cargar asesores"
          message={operatingQuery.error instanceof Error ? operatingQuery.error.message : 'Error de API'}
          onRetry={() => void operatingQuery.refetch()}
        />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white px-6 py-5">
        <Link
          to="/"
          className="mb-3 inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800"
        >
          <ArrowLeft className="h-4 w-4" />
          Volver a operación por marca
        </Link>
        <p className="text-sm uppercase tracking-wide text-blue-600">Detalle de cartera</p>
        <h1 className="text-2xl font-semibold">Negocios por asesor</h1>
        <p className="text-slate-600">
          Llamadas, WhatsApp y cobertura de cartera — misma metodología que la vista por marca y por grupo.
        </p>
      </header>

      <div className="border-b bg-white px-6 py-4">
        <nav className="mb-4 flex flex-wrap gap-2">
          {BRANDS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => selectBrand(item.id)}
              className={`rounded-full px-5 py-2.5 text-sm font-medium ${
                brand === item.id ? 'bg-blue-600 text-white shadow-sm' : 'bg-slate-100 text-slate-700'
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <label className="block text-sm font-medium text-slate-700" htmlFor="advisor-select">
          Asesor
        </label>
        <select
          id="advisor-select"
          className="mt-1 w-full max-w-md rounded-lg border border-slate-200 px-3 py-2 text-sm"
          value={ownerId ?? ''}
          onChange={(e) => {
            if (e.target.value) selectAdvisor(e.target.value)
          }}
        >
          <option value="">Selecciona un asesor…</option>
          {advisors.map((row) => {
            const id = advisorRouteId(row.owner_id)
            return (
              <option key={id} value={id}>
                {row.owner_name ?? 'Sin asignar'} — {row.open_deals} abiertos
              </option>
            )
          })}
        </select>

        {ownerId ? (
          <div className="mt-4">
            <label className="block text-sm font-medium text-slate-700" htmlFor="compare-select">
              Comparar con otro asesor
            </label>
            <select
              id="compare-select"
              className="mt-1 w-full max-w-md rounded-lg border border-slate-200 px-3 py-2 text-sm"
              value={compareOwnerId}
              onChange={(e) => setCompareOwnerId(e.target.value)}
            >
              <option value="">Sin comparación</option>
              {advisors
                .filter((row) => advisorRouteId(row.owner_id) !== ownerId)
                .map((row) => {
                  const id = advisorRouteId(row.owner_id)
                  return (
                    <option key={id} value={id}>
                      {row.owner_name ?? 'Sin asignar'} — {row.open_deals} abiertos
                    </option>
                  )
                })}
            </select>
          </div>
        ) : null}
      </div>

      <main className="space-y-6 p-6">
        {!ownerId ? (
          <section className="rounded-xl border bg-white p-8 text-center shadow-sm">
            <p className="text-slate-600">Elige un asesor para ver su cartera en {brand.toUpperCase()}.</p>
          </section>
        ) : portfolioQuery.isPending && !portfolioQuery.data ? (
          <SlowLoadNotice title="Cargando cartera del asesor…" />
        ) : portfolioQuery.error ? (
          <ErrorState
            title="No se pudo cargar la cartera"
            message={portfolioQuery.error instanceof Error ? portfolioQuery.error.message : 'Error de API'}
            onRetry={() => void portfolioQuery.refetch()}
          />
        ) : portfolio ? (
          <>
            {wonSales ? (
              <section className="rounded-xl border bg-white p-5 shadow-sm">
                <h2 className="mb-1 text-lg font-medium">Ventas de {portfolio.advisor.owner_name}</h2>
                <p className="mb-3 text-sm text-slate-500">Unidades cerradas ganadas asignadas al asesor.</p>
                <WonSalesSummaryStrip
                  summary={wonSales}
                  historicalHint="Cierres ganados históricos del asesor"
                />
              </section>
            ) : null}

            <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-6">
              <SummaryKpi label="Negocios asignados" value={portfolio.summary.assigned_deals} />
              <SummaryKpi label="Abiertos" value={portfolio.summary.open_deals} />
              <SummaryKpi
                label="Cobertura llamadas"
                value={
                  portfolio.summary.call_coverage_rate != null
                    ? formatPercent(portfolio.summary.call_coverage_rate)
                    : '—'
                }
                isText
              />
              <SummaryKpi
                label="Cobertura WhatsApp"
                value={
                  portfolio.summary.whatsapp_coverage_rate != null
                    ? formatPercent(portfolio.summary.whatsapp_coverage_rate)
                    : '—'
                }
                isText
              />
              <SummaryKpi
                label="Cobertura combinada"
                value={
                  portfolio.summary.combined_coverage_rate != null
                    ? formatPercent(portfolio.summary.combined_coverage_rate)
                    : '—'
                }
                isText
              />
              <SummaryKpi
                label="Sin llamada ni WhatsApp en 21 días"
                value={
                  portfolio.summary.channel_overdue_21d ??
                  portfolio.summary.overdue_contact_21d ??
                  '—'
                }
                accent="warning"
              />
            </section>

            <ContactMethodologySection
              data={portfolio.contact_methodology}
              contactWindowDays={portfolio.contact_methodology?.contact_window_days ?? 21}
            />

            {comparePortfolio ? (
              <section className="grid gap-4 rounded-xl border bg-slate-50 p-4 md:grid-cols-2">
                <CompareStat
                  label={portfolio.advisor.owner_name}
                  open={portfolio.summary.open_deals}
                  callCoverage={portfolio.summary.call_coverage_rate}
                  combinedCoverage={portfolio.summary.combined_coverage_rate}
                  discipline={portfolio.summary.discipline_contact_score}
                />
                <CompareStat
                  label={comparePortfolio.advisor.owner_name}
                  open={comparePortfolio.summary.open_deals}
                  callCoverage={comparePortfolio.summary.call_coverage_rate}
                  combinedCoverage={comparePortfolio.summary.combined_coverage_rate}
                  discipline={comparePortfolio.summary.discipline_contact_score}
                  muted
                />
              </section>
            ) : null}

            <ChartCard
              title="Negocios creados por semana"
              description={
                comparePortfolio
                  ? `Comparativa con ${comparePortfolio.advisor.owner_name} — historial completo`
                  : 'Negocios asignados al asesor creados cada semana — historial completo'
              }
            >
              <AdvisorWeeklyChart data={weeklyCreatedChart} />
            </ChartCard>

            <div className="grid gap-6 lg:grid-cols-2">
              <ChartCard
                title="Cartera abierta por grupo de etapa"
                description={`Cuántos negocios abiertos hay en cada fase comercial y cuántos llevan ${brand === 'shacman' ? '45+' : '21+'} días sin actividad.`}
              >
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={portfolio.charts.by_commercial_group} layout="vertical" margin={{ left: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                      <YAxis
                        type="category"
                        dataKey="commercial_group_label"
                        width={110}
                        tick={{ fontSize: 10 }}
                      />
                      <Tooltip />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="open_deals" name="Abiertos" fill="#2563eb" radius={4} />
                      <Bar dataKey="stale_45d" name={staleSeriesLabel} fill="#f97316" radius={4} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>

              <ChartCard
                title="Cobertura de contacto (abiertos)"
                description="Negocios únicos con llamada, WhatsApp, sin gestión reciente o multicanal en ventana 21d."
              >
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={portfolio.charts.open_health}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-12} textAnchor="end" height={56} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="count" name="Negocios" fill="#2563eb" radius={4} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>

              <ChartCard
                title="Días sin actividad (abiertos)"
                description="Distribución de inactividad en la cartera abierta del asesor."
              >
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={portfolio.charts.inactivity_distribution}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="bucket" tick={{ fontSize: 10 }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="count" name="Negocios" fill="#14b8a6" radius={4} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>

              <ChartCard
                title="Top etapas con más abiertos"
                description="Etapas HubSpot con mayor concentración de cartera activa."
              >
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={portfolio.charts.by_stage} layout="vertical" margin={{ left: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                      <YAxis type="category" dataKey="stage_label" width={120} tick={{ fontSize: 10 }} />
                      <Tooltip />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="count" name="Abiertos" fill="#2563eb" radius={4} />
                      <Bar dataKey="stale_45d" name={staleSeriesLabel} fill="#f97316" radius={4} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
            </div>

            {portfolio.activity_coverage_note ? (
              <p className="text-sm text-slate-500">{portfolio.activity_coverage_note}</p>
            ) : null}

            <section className="space-y-4 rounded-xl border bg-white p-5 shadow-sm">
              <div>
                <h2 className="text-lg font-medium">Tareas de {portfolio.advisor.owner_name}</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Solo tareas vinculadas a un contacto o negocio en HubSpot.
                  {taskCounts?.excluded_orphan ? (
                    <>
                      {' '}
                      Excluidas {taskCounts.excluded_orphan.toLocaleString('es-CO')} huérfanas (sin contacto ni
                      negocio).
                    </>
                  ) : null}
                  {taskCounts?.excluded_reassigned_lead ? (
                    <>
                      {' '}
                      Excluidas {taskCounts.excluded_reassigned_lead.toLocaleString('es-CO')} de reasignación
                      («Perdiste este Lead»).
                    </>
                  ) : null}
                  {taskCounts?.excluded_closed_deal ? (
                    <>
                      {' '}
                      Excluidas {taskCounts.excluded_closed_deal.toLocaleString('es-CO')} de negocios en cierre
                      ganado/perdido.
                    </>
                  ) : null}
                </p>
              </div>

              <div className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-100 bg-slate-50 p-3">
                <div className="flex flex-wrap gap-2">
                  {TASK_FILTERS.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setTaskFilter(item.id)}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                        taskFilter === item.id
                          ? 'bg-blue-600 text-white'
                          : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {item.label} ({taskFilterCounts[item.id].toLocaleString('es-CO')})
                    </button>
                  ))}
                </div>
                <span className="hidden h-6 w-px bg-slate-200 sm:block" aria-hidden />
                <div className="flex flex-wrap gap-2">
                  {TASK_TIME_FILTERS.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setTaskTimeFilter(item.id)}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                        taskTimeFilter === item.id
                          ? 'bg-violet-600 text-white'
                          : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                {taskTimeFilter === 'custom_due' ? (
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <label className="flex items-center gap-1 text-slate-600">
                      Desde
                      <input
                        type="date"
                        className="rounded border border-slate-200 px-2 py-1 text-sm"
                        value={taskDueFrom}
                        onChange={(e) => setTaskDueFrom(e.target.value)}
                      />
                    </label>
                    <label className="flex items-center gap-1 text-slate-600">
                      Hasta
                      <input
                        type="date"
                        className="rounded border border-slate-200 px-2 py-1 text-sm"
                        value={taskDueTo}
                        onChange={(e) => setTaskDueTo(e.target.value)}
                      />
                    </label>
                  </div>
                ) : null}
              </div>

              <p className="text-sm text-slate-500">
                Mostrando{' '}
                <span className="font-medium text-slate-700">
                  {filteredTasks.length.toLocaleString('es-CO')}
                </span>{' '}
                · {TASK_FILTERS.find((f) => f.id === taskFilter)?.label} ·{' '}
                {TASK_TIME_FILTERS.find((f) => f.id === taskTimeFilter)?.label}
              </p>

              <AdvisorTaskTable
                tasks={filteredTasks}
                resetKey={`${taskFilter}-${taskTimeFilter}-${taskDueFrom}-${taskDueTo}`}
              />
            </section>
          </>
        ) : null}
      </main>
    </div>
  )
}

function SummaryKpi({
  label,
  value,
  accent,
  isText,
}: {
  label: string
  value: number | string
  accent?: 'warning'
  isText?: boolean
}) {
  return (
    <article className="rounded-xl border bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p
        className={`mt-2 font-semibold ${isText ? 'text-2xl' : 'text-3xl'} ${
          accent === 'warning' ? 'text-orange-600' : ''
        }`}
      >
        {typeof value === 'number' ? value.toLocaleString('es-CO') : value}
      </p>
    </article>
  )
}

function AdvisorWeeklyChart({
  data,
  colorA = '#2563eb',
  colorB = '#8b5cf6',
}: {
  data: Array<Record<string, string | number>>
  colorA?: string
  colorB?: string
}) {
  const seriesKeys = Object.keys(data[0] ?? {}).filter((k) => k !== 'week_start')
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="week_start" tick={{ fontSize: 10 }} interval={weekAxisInterval(data.length)} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {seriesKeys.map((key, index) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              name={key}
              stroke={index === 0 ? colorA : colorB}
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function CompareStat({
  label,
  open,
  callCoverage,
  combinedCoverage,
  discipline,
  muted,
}: {
  label: string
  open: number
  callCoverage: number | null | undefined
  combinedCoverage: number | null | undefined
  discipline: number | null | undefined
  muted?: boolean
}) {
  return (
    <article className={`rounded-lg border bg-white p-4 ${muted ? 'opacity-90' : ''}`}>
      <p className="font-medium text-slate-800">{label}</p>
      <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
        <div>
          <dt className="text-slate-500">Abiertos</dt>
          <dd className="font-semibold">{open.toLocaleString('es-CO')}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Cob. llamadas</dt>
          <dd className="font-semibold">{callCoverage != null ? formatPercent(callCoverage) : '—'}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Cob. combinada</dt>
          <dd className="font-semibold">{combinedCoverage != null ? formatPercent(combinedCoverage) : '—'}</dd>
        </div>
        <div className="col-span-3">
          <dt className="text-slate-500">Disciplina contacto</dt>
          <dd className="font-semibold text-blue-700">{discipline ?? '—'}</dd>
        </div>
      </dl>
    </article>
  )
}
