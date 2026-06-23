import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ChartCard } from '@/components/charts/ChartCard'
import { MonthOverMonthBadge } from '@/components/deal-analytics/MonthOverMonthBadge'
import { PaginatedMetricTable } from '@/components/deal-analytics/PaginatedMetricTable'
import { AdvisorCompareCharts } from '@/components/deal-analytics/AdvisorCompareCharts'
import { WonSalesSummaryStrip } from '@/components/deal-analytics/WonSalesSummaryStrip'
import { ErrorState } from '@/components/ui/ErrorState'
import { SlowLoadNotice } from '@/components/ui/SlowLoadNotice'
import { useBrandOperating, type OperatingBrand } from '@/hooks/useBrandOperating'
import { buildBrandAdvisorTableColumns } from '@/lib/brandAdvisorTableColumns'
import { staleChartSeriesLabel, staleMetricLongLabel, staleMetricTooltip, staleThresholdDays } from '@/lib/brandStale'
import { BRAND_KPI_TOOLTIPS } from '@/lib/metricTooltips'
import { advisorPortfolioPath } from '@/lib/advisorRoutes'
import { formatPercent, formatCopAbbrev } from '@/lib/format'
import { weekAxisInterval } from '@/lib/chartTicks'
import {
  addWeeklyTrend,
  enrichClosedWeeklySeries,
  periodOverPeriodChange,
  trendDescriptionSuffix,
  trendLegendLabel,
} from '@/lib/weeklyTrends'
import { HelpCircle, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useExportBrandAdvisors } from '@/hooks/useExportBrandAdvisors'

const BRANDS: { id: OperatingBrand; label: string }[] = [
  { id: 'voyah', label: 'Voyah' },
  { id: 'mhero', label: 'MHero' },
  { id: 'shacman', label: 'Shacman' },
]

export function BrandOperatingPage() {
  const [brand, setBrand] = useState<OperatingBrand>('voyah')
  const { data, isPending, error, refetch } = useBrandOperating(brand)
  const { exportExcel, exportAllBrands, exporting, exportingAll, error: exportError } = useExportBrandAdvisors(brand)
  const operating = data?.data
  const showLoader = isPending && !operating

  const weeklyCreatedChart = useMemo(
    () => addWeeklyTrend(operating?.weekly_created ?? [], 'deals_created', 'ema'),
    [operating?.weekly_created],
  )
  const weeklyCallsChart = useMemo(
    () => addWeeklyTrend(operating?.weekly_calls ?? [], 'calls', 'ema'),
    [operating?.weekly_calls],
  )

  const callsPeriodLabel = useMemo(
    () => periodOverPeriodChange((operating?.weekly_calls ?? []).map((row) => row.calls)).label,
    [operating?.weekly_calls],
  )
  const createdPeriodLabel = useMemo(
    () =>
      periodOverPeriodChange((operating?.weekly_created ?? []).map((row) => row.deals_created)).label,
    [operating?.weekly_created],
  )

  const weeklyWonWithTrends = useMemo(
    () => enrichClosedWeeklySeries(operating?.weekly_won ?? []),
    [operating?.weekly_won],
  )
  const weeklyLostWithTrends = useMemo(
    () => enrichClosedWeeklySeries(operating?.weekly_lost ?? []),
    [operating?.weekly_lost],
  )

  const wonCountPeriodLabel = useMemo(
    () =>
      periodOverPeriodChange((operating?.weekly_won ?? []).map((row) => row.deals_closed)).label,
    [operating?.weekly_won],
  )
  const wonAmountPeriodLabel = useMemo(
    () =>
      periodOverPeriodChange((operating?.weekly_won ?? []).map((row) => row.total_amount)).label,
    [operating?.weekly_won],
  )
  const lostCountPeriodLabel = useMemo(
    () =>
      periodOverPeriodChange((operating?.weekly_lost ?? []).map((row) => row.deals_closed)).label,
    [operating?.weekly_lost],
  )

  const staleDays = staleThresholdDays(brand, operating?.stale_threshold_days)
  const staleKpiLabel = staleMetricLongLabel(brand, operating?.stale_threshold_days)
  const staleSeriesLabel = staleChartSeriesLabel(brand, operating?.stale_threshold_days)
  const advisorTableColumns = useMemo(
    () => buildBrandAdvisorTableColumns(brand, operating?.stale_threshold_days),
    [brand, operating?.stale_threshold_days],
  )

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <ErrorState
          title="No se pudo cargar la marca"
          message={error instanceof Error ? error.message : 'Error de API'}
          onRetry={() => void refetch()}
        />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white px-6 py-5">
        <p className="text-sm uppercase tracking-wide text-blue-600">Operación comercial por marca</p>
        <h1 className="text-2xl font-semibold">Cada marca, su propio mundo</h1>
        <p className="text-slate-600">
          Etapas por semántica comercial · Asesores por marca · Negocios nuevos y estancados
        </p>
        <Link
          to="/asesor"
          className="mt-3 mr-4 inline-block text-sm font-medium text-blue-600 hover:text-blue-800"
        >
          Ver detalle de cartera por asesor →
        </Link>
        <Link
          to="/grupo"
          className="mt-3 inline-block text-sm font-medium text-blue-600 hover:text-blue-800"
        >
          Comparar grupos de asesores →
        </Link>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="outline"
            disabled={exporting || exportingAll}
            onClick={() => void exportExcel()}
            className="gap-2"
          >
            <Download className="h-4 w-4" aria-hidden />
            {exporting
              ? 'Generando Excel…'
              : `Exportar ${BRANDS.find((b) => b.id === brand)?.label ?? brand}`}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={exporting || exportingAll}
            onClick={() => void exportAllBrands()}
            className="gap-2"
          >
            <Download className="h-4 w-4" aria-hidden />
            {exportingAll ? 'Generando 3 archivos…' : 'Exportar las 3 marcas'}
          </Button>
          <p className="text-xs text-slate-500">
            Excel analítico por marca: asesores, ventas, contacto, rendimiento mensual, tendencias y metodología.
          </p>
          {exportError ? <p className="w-full text-sm text-red-600">{exportError}</p> : null}
        </div>
      </header>

      <div className="border-b bg-white px-6 py-4">
        <nav className="flex flex-wrap gap-2">
          {BRANDS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setBrand(item.id)}
              className={`rounded-full px-5 py-2.5 text-sm font-medium ${
                brand === item.id ? 'bg-blue-600 text-white shadow-sm' : 'bg-slate-100 text-slate-700'
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
        {operating?.activity_coverage_note && (
          <p className="mt-3 text-sm text-slate-500">{operating.activity_coverage_note}</p>
        )}
      </div>

      <main className="space-y-6 p-6">
        {showLoader ? (
          <SlowLoadNotice title={`Cargando ${brand.toUpperCase()}…`} />
        ) : operating ? (
          <>
            <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-6">
              <Kpi label="Negocios abiertos" value={operating.totals.open_deals} />
              <Kpi label="Nuevos 7 días" value={operating.totals.new_deals_7d} />
              <Kpi
                label="Cobertura llamadas"
                value={operating.contact_methodology?.brand_summary?.calls?.call_coverage_rate}
                isPercent
              />
              <Kpi
                label="Cobertura WhatsApp"
                value={operating.contact_methodology?.brand_summary?.whatsapp?.whatsapp_coverage_rate}
                isPercent
              />
              <Kpi
                label="Cobertura combinada"
                value={operating.contact_methodology?.brand_summary?.coverage?.combined_contact_coverage_rate}
                isPercent
              />
              <Kpi
                label={staleKpiLabel}
                value={operating.totals.stale_45d_open}
                accent="warning"
                tooltip={staleMetricTooltip(brand, operating?.stale_threshold_days)}
              />
            </section>

            <ChartCard
              title="Embudo por grupo comercial de etapa"
              description="Agrupa cotización/financiera, venta, operaciones y cierres — no mezcla etapas crudas de HubSpot"
            >
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={operating.stage_groups} layout="vertical" margin={{ left: 120 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" allowDecimals={false} />
                    <YAxis
                      type="category"
                      dataKey="commercial_group_label"
                      width={115}
                      tick={{ fontSize: 11 }}
                    />
                    <Tooltip />
                    <Bar dataKey="open_deals" fill="#2563eb" name="Abiertos" radius={4} />
                    <Bar dataKey="stale_45d" fill="#f97316" name={staleSeriesLabel} radius={4} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            <section className="overflow-x-auto rounded-xl border bg-white p-4 shadow-sm">
              <h2 className="mb-4 text-lg font-medium">Detalle de etapas dentro de cada grupo</h2>
              <div className="grid gap-4 lg:grid-cols-2">
                {operating.stage_groups.map((group) => (
                  <div key={group.commercial_group} className="rounded-lg border p-3">
                    <h3 className="font-medium text-slate-800">{group.commercial_group_label}</h3>
                    <p className="text-sm text-slate-500">
                      {group.open_deals} abiertos · {group.stale_45d} estancados {staleDays}d
                    </p>
                    <ul className="mt-2 space-y-1 text-sm">
                      {group.stages_detail.map((s) => (
                        <li key={s.stage_label} className="flex justify-between">
                          <span className="text-slate-600">{s.stage_label}</span>
                          <span className="font-medium">{s.count}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </section>

            <div className="grid gap-6 lg:grid-cols-2">
              <ChartCard
                title="Llamadas por semana"
                description={
                  weeklyCallsChart.length > 0
                    ? trendDescriptionSuffix('ema', callsPeriodLabel)
                    : 'Sin llamadas sincronizadas en el periodo actual. Amplía la ventana de sync de actividades si necesitas más historial.'
                }
              >
                {weeklyCallsChart.length > 0 ? (
                  <WeeklyLineChart
                    data={weeklyCallsChart}
                    countKey="calls"
                    countLabel="Llamadas"
                    trendKey="trend"
                    trendLabel={trendLegendLabel('ema')}
                  />
                ) : (
                  <p className="py-12 text-center text-sm text-slate-500">
                    No hay llamadas sincronizadas asociadas a los negocios de esta marca.
                  </p>
                )}
              </ChartCard>

              <ChartCard
                title="Negocios creados por semana"
                description={trendDescriptionSuffix('ema', createdPeriodLabel)}
              >
                <WeeklyLineChart
                  data={weeklyCreatedChart}
                  countKey="deals_created"
                  countLabel="Creados"
                  trendKey="trend"
                  trendLabel={trendLegendLabel('ema')}
                />
              </ChartCard>

              <ChartCard
                title="Ventas cerradas ganadas por semana"
                description={`Cantidad en línea · monto en barras · ${trendDescriptionSuffix('rolling_sum', wonCountPeriodLabel)} · Montos: ${wonAmountPeriodLabel || 'comparativa no disponible'}`}
              >
                {operating.won_sales_summary ? (
                  <WonSalesSummaryStrip summary={operating.won_sales_summary} />
                ) : null}
                <WeeklyClosedChart
                  data={weeklyWonWithTrends}
                  countLabel="Ganados"
                  color="#22c55e"
                  countTrendKey="count_trend"
                  amountTrendKey="amount_trend"
                  countTrendLabel={trendLegendLabel('rolling_sum')}
                  amountTrendLabel={trendLegendLabel('rolling_median')}
                />
              </ChartCard>

              <ChartCard
                title="Ventas cerradas perdidas por semana"
                description={`Cantidad en línea · monto en barras · ${trendDescriptionSuffix('rolling_sum', lostCountPeriodLabel)}`}
              >
                <WeeklyClosedChart
                  data={weeklyLostWithTrends}
                  countLabel="Perdidos"
                  color="#ef4444"
                  countTrendKey="count_trend"
                  amountTrendKey="amount_trend"
                  countTrendLabel={trendLegendLabel('rolling_sum')}
                  amountTrendLabel={trendLegendLabel('rolling_median')}
                />
              </ChartCard>
            </div>

            <PaginatedMetricTable
              title={`Gestión de asesores en ${operating.brand_label}`}
              description="Un mismo asesor en varias marcas aparece separado por marca. Desplaza horizontalmente si necesitas ver todas las columnas. Haz clic en el nombre para ver su cartera."
              columns={advisorTableColumns}
              resetKey={brand}
              rows={operating.advisors.map((row) => [
                <Link
                  key={row.owner_id ?? 'unassigned'}
                  to={advisorPortfolioPath(brand, row.owner_id)}
                  className="font-medium text-blue-600 hover:text-blue-800 hover:underline"
                >
                  {row.owner_name ?? 'Sin asignar'}
                </Link>,
                row.open_deals,
                row.new_deals_7d,
                row.new_deals_30d,
                row.stale_45d_open,
                row.tasks_completed,
                row.tasks_open,
                row.tasks_overdue,
                row.deals_with_overdue_tasks,
                row.managed_30d_rate != null ? formatPercent(row.managed_30d_rate) : '—',
                row.call_coverage_rate != null ? formatPercent(row.call_coverage_rate) : '—',
                row.whatsapp_coverage_rate != null ? formatPercent(row.whatsapp_coverage_rate) : '—',
                row.combined_coverage_rate != null ? formatPercent(row.combined_coverage_rate) : '—',
                row.overdue_contact_21d ?? '—',
                row.won_sales?.total_units ?? '—',
                row.won_sales?.units_this_month ?? '—',
                row.won_sales ? <MonthOverMonthBadge summary={row.won_sales} /> : '—',
              ])}
            />

            <AdvisorCompareCharts
              advisors={operating.advisors}
              brandKey={brand}
              brandLabel={operating.brand_label}
              staleDays={staleDays}
            />
          </>
        ) : null}
      </main>
    </div>
  )
}

function Kpi({
  label,
  value,
  accent,
  isPercent,
  tooltip,
}: {
  label: string
  value: number | null | undefined
  accent?: 'warning'
  isPercent?: boolean
  tooltip?: string
}) {
  const resolvedTooltip = tooltip ?? BRAND_KPI_TOOLTIPS[label]
  const display =
    value == null
      ? '—'
      : isPercent
        ? formatPercent(value)
        : value.toLocaleString('es-CO')
  return (
    <article className="rounded-xl border bg-white p-4 shadow-sm">
      <div className="group relative inline-flex items-center gap-1.5">
        <p className="text-sm text-slate-500">{label}</p>
        {resolvedTooltip ? (
          <>
            <HelpCircle className="h-3.5 w-3.5 text-slate-400" aria-hidden />
            <span
              role="tooltip"
              className="pointer-events-none absolute bottom-full left-0 z-30 mb-2 hidden w-64 rounded-lg bg-slate-900 px-3 py-2 text-xs font-normal leading-relaxed text-white shadow-lg group-hover:block"
            >
              {resolvedTooltip}
            </span>
          </>
        ) : null}
      </div>
      <p className={`mt-2 text-3xl font-semibold ${accent === 'warning' ? 'text-orange-600' : ''}`}>
        {display}
      </p>
    </article>
  )
}

function WeeklyLineChart({
  data,
  countKey,
  countLabel,
  compareKey,
  compareLabel,
  trendKey,
  trendLabel = 'Tendencia',
}: {
  data: Array<Record<string, string | number | null>>
  countKey: string
  countLabel: string
  compareKey?: string
  compareLabel?: string
  trendKey?: string
  trendLabel?: string
}) {
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="week_start" tick={{ fontSize: 10 }} interval={weekAxisInterval(data.length)} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey={countKey} name={countLabel} stroke="#2563eb" strokeWidth={2} />
          {trendKey ? (
            <Line
              type="monotone"
              dataKey={trendKey}
              name={trendLabel}
              stroke="#64748b"
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={false}
            />
          ) : null}
          {compareKey && compareLabel ? (
            <Line type="monotone" dataKey={compareKey} name={compareLabel} stroke="#8b5cf6" strokeWidth={2} />
          ) : null}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function WeeklyClosedChart({
  data,
  countLabel,
  color,
  countTrendKey,
  amountTrendKey,
  countTrendLabel = 'Tendencia cantidad',
  amountTrendLabel = 'Tendencia monto',
}: {
  data: Array<{
    week_start: string
    deals_closed: number
    total_amount: number
    count_trend?: number | null
    amount_trend?: number | null
  }>
  countLabel: string
  color: string
  countTrendKey?: string
  amountTrendKey?: string
  countTrendLabel?: string
  amountTrendLabel?: string
}) {
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="week_start" tick={{ fontSize: 10 }} interval={weekAxisInterval(data.length)} />
          <YAxis yAxisId="left" allowDecimals={false} tick={{ fontSize: 11 }} />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: 10 }}
            tickFormatter={(v) => formatCopAbbrev(Number(v))}
          />
          <Tooltip
            formatter={(value, name) =>
              name === 'Monto' || name === 'Tendencia monto'
                ? formatCopAbbrev(Number(value))
                : Number(value).toLocaleString('es-CO')
            }
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar
            yAxisId="right"
            dataKey="total_amount"
            name="Monto"
            fill={color}
            fillOpacity={0.35}
            radius={[3, 3, 0, 0]}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="deals_closed"
            name={countLabel}
            stroke={color}
            strokeWidth={2}
            dot={false}
          />
          {countTrendKey ? (
            <Line
              yAxisId="left"
              type="monotone"
              dataKey={countTrendKey}
              name={countTrendLabel}
              stroke="#64748b"
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={false}
            />
          ) : null}
          {amountTrendKey ? (
            <Line
              yAxisId="right"
              type="monotone"
              dataKey={amountTrendKey}
              name={amountTrendLabel}
              stroke="#94a3b8"
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={false}
            />
          ) : null}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
