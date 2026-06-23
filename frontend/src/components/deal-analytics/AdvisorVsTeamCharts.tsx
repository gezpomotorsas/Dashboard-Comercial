import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { MonthOverMonthBadge } from '@/components/deal-analytics/MonthOverMonthBadge'
import { WonSalesSummaryStrip } from '@/components/deal-analytics/WonSalesSummaryStrip'
import { MetricTableLayout } from '@/components/ui/MetricTableLayout'
import {
  advisorPerformance,
  buildAdvisorVsTeamComparison,
  vsTeamLabel,
  type AdvisorPerformanceCompareRow,
  type CompareReference,
  type VsTeamVerdict,
} from '@/lib/advisorTeamCompare'
import { advisorPortfolioPath } from '@/lib/advisorRoutes'
import type { MetricColumn } from '@/lib/metricTooltips'
import type { BrandAdvisorRow } from '@/types/dealAnalytics'

const COMPARE_COLUMNS: MetricColumn[] = [
  { label: 'Métrica', tooltip: 'Indicador de rendimiento operativo.', sticky: true, minWidth: 160 },
  {
    label: 'Este mes (asesor)',
    tooltip: 'Valor del asesor: total histórico, unidades del mes o indicador según la métrica.',
    align: 'right',
    minWidth: 110,
  },
  {
    label: 'vs mes anterior',
    tooltip: 'Mes anterior en unidades o variación porcentual (ventas y métricas mensuales).',
    align: 'center',
    minWidth: 140,
  },
  {
    label: 'Media del grupo',
    tooltip: 'Promedio de los compañeros del equipo de referencia en el mes actual.',
    align: 'right',
    minWidth: 110,
  },
  {
    label: 'vs grupo',
    tooltip: 'Si el asesor está por encima, por debajo o similar al promedio del grupo.',
    align: 'center',
    minWidth: 150,
  },
]

const verdictClass: Record<Exclude<VsTeamVerdict, null>, string> = {
  above: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  below: 'border-red-200 bg-red-50 text-red-700',
  similar: 'border-slate-200 bg-slate-100 text-slate-700',
}

function VsTeamBadge({ verdict }: { verdict: VsTeamVerdict }) {
  if (verdict == null) return <span className="text-slate-400">—</span>
  return (
    <span
      className={`inline-flex rounded-lg border px-2.5 py-1.5 text-xs font-medium ${verdictClass[verdict]}`}
    >
      {vsTeamLabel(verdict)}
    </span>
  )
}

function formatCount(value: number | null): string {
  if (value == null) return '—'
  return value.toLocaleString('es-CO')
}

function formatMomTeamAvg(value: number | null): string {
  if (value == null) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value}%`
}

function rowCells(row: AdvisorPerformanceCompareRow) {
  if (row.variant === 'total') {
    return [
      row.label,
      formatCount(row.advisorThisMonth),
      '—',
      formatCount(row.teamAvgThisMonth),
      <VsTeamBadge key={row.key} verdict={row.vsTeam} />,
    ]
  }

  if (row.variant === 'month') {
    const showPrev =
      row.advisorMom.units_this_month > 0 || row.advisorMom.units_previous_month > 0
    return [
      row.label,
      formatCount(row.advisorThisMonth),
      showPrev ? formatCount(row.advisorPreviousMonth) : '—',
      formatCount(row.teamAvgThisMonth),
      <VsTeamBadge key={row.key} verdict={row.vsTeam} />,
    ]
  }

  if (row.variant === 'mom') {
    const showMom =
      row.advisorMom.units_this_month > 0 || row.advisorMom.units_previous_month > 0
    return [
      row.label,
      formatCount(row.advisorThisMonth),
      showMom ? <MonthOverMonthBadge summary={row.advisorMom} /> : '—',
      formatMomTeamAvg(row.teamAvgThisMonth),
      '—',
    ]
  }

  const showMom =
    row.advisorMom.units_this_month > 0 ||
    row.advisorMom.units_previous_month > 0 ||
    row.key === 'tasks_overdue'

  return [
    row.label,
    formatCount(row.advisorThisMonth),
    showMom ? <MonthOverMonthBadge summary={row.advisorMom} /> : '—',
    formatCount(row.teamAvgThisMonth),
    <VsTeamBadge key={row.key} verdict={row.vsTeam} />,
  ]
}

export function AdvisorVsTeamCharts({
  advisor,
  advisors,
  compareReference,
  brandKey,
  brandLabel,
}: {
  advisor: BrandAdvisorRow
  advisors: BrandAdvisorRow[]
  compareReference: CompareReference
  brandKey: string
  brandLabel: string
}) {
  const comparison = useMemo(
    () => buildAdvisorVsTeamComparison(advisor, advisors, compareReference),
    [advisor, advisors, compareReference],
  )

  const portfolioPath = advisorPortfolioPath(brandKey, advisor.owner_id)
  const advisorName = advisor.owner_name ?? 'Asesor'
  const salesSummary = advisor.won_sales ?? advisorPerformance(advisor).won_sales

  const tableRows = useMemo(
    () => comparison.rows.map((row) => rowCells(row)),
    [comparison.rows],
  )

  if (comparison.context.peerCount === 0) {
    return (
      <section className="rounded-xl border bg-white p-6 shadow-sm">
        <p className="text-sm text-slate-600">
          No hay compañeros comparables para {advisorName} en {brandLabel}. El asesor es el único del equipo
          detectado con cartera en esta marca.
        </p>
      </section>
    )
  }

  return (
    <section className="space-y-4 rounded-xl border bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-medium text-slate-900">
          {advisorName} vs media del grupo — {brandLabel}
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Referencia:{' '}
          <span className="font-medium text-slate-700">{comparison.context.teamName}</span> ·{' '}
          {comparison.context.peerCount} compañero{comparison.context.peerCount === 1 ? '' : 's'} · ventas,
          leads, tareas (completadas, gestionadas, atrasadas) y contacto del mes calendario actual comparados con el
          promedio del grupo.
        </p>
        <Link to={portfolioPath} className="mt-2 inline-block text-sm text-blue-600 hover:underline">
          Ver cartera completa de {advisorName}
        </Link>
      </div>

      {(salesSummary.total_units > 0 ||
        salesSummary.units_this_month > 0 ||
        salesSummary.units_previous_month > 0) && (
        <WonSalesSummaryStrip summary={salesSummary} />
      )}

      <MetricTableLayout columns={COMPARE_COLUMNS} rows={tableRows} />
    </section>
  )
}
