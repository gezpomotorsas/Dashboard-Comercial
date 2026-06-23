import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type {
  ContactMethodologyData,
  ContactMetricsCalls,
  ContactMetricsCoverage,
  ContactMetricsEvaluation,
  ContactMetricsWhatsapp,
} from '@/types/contactMetrics'
import { ChartCard } from '@/components/charts/ChartCard'
import { formatPercent } from '@/lib/format'
import { weekAxisInterval } from '@/lib/chartTicks'

const CHANNEL_COLORS: Record<string, string> = {
  'Sin gestión reciente': '#94a3b8',
  'Solo llamada': '#2563eb',
  'Solo WhatsApp': '#22c55e',
  'Llamada y WhatsApp': '#8b5cf6',
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—'
  if (seconds < 60) return `${Math.round(seconds)} s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  return secs > 0 ? `${mins} min ${secs} s` : `${mins} min`
}

function DataStatusBadge({ status }: { status?: string }) {
  if (!status) return null
  const styles: Record<string, string> = {
    available: 'bg-green-100 text-green-800',
    partial: 'bg-amber-100 text-amber-800',
    insufficient: 'bg-orange-100 text-orange-800',
    unavailable: 'bg-slate-100 text-slate-600',
    estimated: 'bg-violet-100 text-violet-800',
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[status] ?? styles.unavailable}`}>
      {status}
    </span>
  )
}

export function ContactMethodologySection({
  data,
  contactWindowDays = 21,
}: {
  data: ContactMethodologyData | null | undefined
  contactWindowDays?: number
}) {
  if (!data) {
    return (
      <section className="rounded-xl border border-dashed bg-white p-6 text-sm text-slate-500">
        Métricas de llamadas y WhatsApp no disponibles para este asesor.
      </section>
    )
  }

  const calls: ContactMetricsCalls = data.calls ?? {
    total_calls: 0,
    unique_deals_called: 0,
    call_coverage_rate: null,
  }
  const wa: ContactMetricsWhatsapp = data.whatsapp ?? {
    whatsapp_messages: 0,
    unique_deals_with_whatsapp: 0,
    whatsapp_coverage_rate: null,
  }
  const cov: ContactMetricsCoverage = data.coverage ?? {
    combined_contact_coverage_rate: null,
  }
  const ev: ContactMetricsEvaluation = data.evaluation ?? {}

  const channelPie = [
    { name: 'Sin gestión reciente', value: cov.deals_no_recent_contact ?? 0 },
    { name: 'Solo llamada', value: cov.deals_call_only ?? 0 },
    { name: 'Solo WhatsApp', value: cov.deals_whatsapp_only ?? 0 },
    { name: 'Llamada y WhatsApp', value: cov.deals_multichannel ?? 0 },
  ].filter((d) => d.value > 0)

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <KpiCard label="Negocios activos" value={String(data.active_deals ?? '—')} />
        <KpiCard
          label="Cobertura llamadas"
          value={calls.call_coverage_rate != null ? formatPercent(calls.call_coverage_rate) : '—'}
          sub={`${calls.call_coverage_numerator ?? 0}/${calls.call_coverage_denominator ?? 0} neg.`}
        />
        <KpiCard
          label="Cobertura WhatsApp"
          value={wa.whatsapp_coverage_rate != null ? formatPercent(wa.whatsapp_coverage_rate) : '—'}
          sub={`${wa.whatsapp_coverage_numerator ?? 0}/${wa.whatsapp_coverage_denominator ?? 0} neg.`}
        />
        <KpiCard
          label="Cobertura combinada"
          value={cov.combined_contact_coverage_rate != null ? formatPercent(cov.combined_contact_coverage_rate) : '—'}
        />
        <KpiCard label="Sin llamada ni WhatsApp en 21 días" value={String(cov.channel_overdue_21d ?? cov.overdue_contact_21d ?? '—')} accent="warning" />
        <KpiCard label="Ganados" value={String(data.won_deals ?? '—')} />
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-xl border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-medium text-slate-700">Disciplina operativa</h3>
          <p className="mt-2 text-3xl font-semibold text-blue-700">
            {ev.discipline_operational_score != null
              ? ev.discipline_operational_score
              : ev.discipline_contact_score != null
                ? ev.discipline_contact_score
                : '—'}
          </p>
          {ev.discipline_operational_status === 'insufficient' ? (
            <p className="mt-1 text-xs text-amber-700">Muestra insuficiente para score completo</p>
          ) : null}
          <p className="mt-1 text-xs text-slate-500">
            Basada en cobertura y recencia ({contactWindowDays}d), no en volumen bruto.
          </p>
        </article>
        <article className="rounded-xl border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-medium text-slate-700">Efectividad comercial</h3>
          <p className="mt-2 text-3xl font-semibold text-emerald-700">
            {ev.effectiveness_commercial_score != null ? ev.effectiveness_commercial_score : '—'}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Cierre {data.close_rate != null ? formatPercent(data.close_rate) : '—'} · {ev.load_classification ?? ''}
          </p>
        </article>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Llamadas" description="Volumen y cobertura por negocio único.">
          <dl className="mb-4 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-slate-500">Total llamadas</dt>
              <dd className="font-semibold">{calls.total_calls ?? 0}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Negocios únicos</dt>
              <dd className="font-semibold">{calls.unique_deals_called ?? 0}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Minutos totales</dt>
              <dd className="font-semibold">
                {calls.total_call_minutes != null ? calls.total_call_minutes.toLocaleString('es-CO') : '—'}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Duración mediana</dt>
              <dd className="flex items-center gap-2 font-semibold">
                {formatDuration(calls.median_call_duration_seconds)}
                <DataStatusBadge status={calls.duration_data_status} />
              </dd>
            </div>
          </dl>
          {calls.duration_note ? <p className="mb-3 text-xs text-amber-700">{calls.duration_note}</p> : null}
          {(calls.duration_ranges?.length ?? 0) > 0 ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={calls.duration_ranges}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="range" tick={{ fontSize: 9 }} interval={0} angle={-20} textAnchor="end" height={70} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" name="Llamadas" fill="#2563eb" radius={4} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : null}
        </ChartCard>

        <ChartCard title="WhatsApp" description="Sesiones estimadas — no conversaciones confirmadas.">
          <dl className="mb-4 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-slate-500">Mensajes</dt>
              <dd className="font-semibold">{wa.whatsapp_messages ?? 0}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Negocios únicos</dt>
              <dd className="font-semibold">{wa.unique_deals_with_whatsapp ?? 0}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Sesiones estimadas</dt>
              <dd className="flex items-center gap-2 font-semibold">
                {wa.estimated_whatsapp_sessions ?? '—'}
                <DataStatusBadge status="estimated" />
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Msj/negocio (prom.)</dt>
              <dd className="font-semibold">{wa.messages_per_deal_average ?? '—'}</dd>
            </div>
          </dl>
          {wa.session_estimation_warning ? (
            <p className="mb-3 text-xs text-violet-800">{wa.session_estimation_warning}</p>
          ) : null}
        </ChartCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {channelPie.length > 0 ? (
          <ChartCard title="Cobertura combinada por canal" description={`Ventana ${contactWindowDays}d`}>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={channelPie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                    {channelPie.map((entry) => (
                      <Cell key={entry.name} fill={CHANNEL_COLORS[entry.name] ?? '#64748b'} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>
        ) : null}

        {(calls.weekly_trend?.length ?? 0) > 0 || (wa.weekly_trend?.length ?? 0) > 0 ? (
          <ChartCard title="Tendencia semanal" description="Llamadas y WhatsApp">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={mergeWeeklyTrends(calls.weekly_trend ?? [], wa.weekly_trend ?? [])}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="week_start"
                    tick={{ fontSize: 10 }}
                    interval={weekAxisInterval((calls.weekly_trend ?? []).length)}
                  />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="calls" name="Llamadas" stroke="#2563eb" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="whatsapp" name="WhatsApp" stroke="#22c55e" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>
        ) : null}
      </div>
    </div>
  )
}

function KpiCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string
  value: string
  sub?: string
  accent?: 'warning'
}) {
  return (
    <article className="rounded-xl border bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${accent === 'warning' ? 'text-orange-600' : ''}`}>{value}</p>
      {sub ? <p className="mt-1 text-xs text-slate-400">{sub}</p> : null}
    </article>
  )
}

function mergeWeeklyTrends(
  calls: Array<{ week_start: string; count: number }>,
  wa: Array<{ week_start: string; count: number }>,
) {
  const keys = new Set([...calls.map((c) => c.week_start), ...wa.map((w) => w.week_start)])
  const callMap = Object.fromEntries(calls.map((c) => [c.week_start, c.count]))
  const waMap = Object.fromEntries(wa.map((w) => [w.week_start, w.count]))
  return [...keys].sort().map((week_start) => ({
    week_start,
    calls: callMap[week_start] ?? 0,
    whatsapp: waMap[week_start] ?? 0,
  }))
}
