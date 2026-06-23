import type { GroupPerformanceMetrics } from '@/types/advisorGroups'
import type { BrandAdvisorRow, WonSalesSummary } from '@/types/dealAnalytics'
import type { AdvisorGroup, HubSpotTeamOption } from '@/types/advisorGroups'

export type CompareReference =
  | { kind: 'team'; id: string; name: string; ownerIds: string[] }
  | { kind: 'group'; id: string; name: string; ownerIds: string[] }
  | { kind: 'brand'; name: string }

export type CompareReferenceOption = {
  key: string
  label: string
  reference: CompareReference
}

export type AdvisorTeamContext = {
  teamId: string | null
  teamName: string
  peerCount: number
  peerOwnerIds: string[]
  referenceKind: CompareReference['kind']
}

export type VsTeamVerdict = 'above' | 'below' | 'similar' | null

export type AdvisorPerformanceCompareRow = {
  key: string
  label: string
  higherIsBetter: boolean
  variant?: 'default' | 'total' | 'month' | 'mom'
  advisorThisMonth: number
  advisorPreviousMonth: number
  advisorMom: WonSalesSummary
  teamAvgThisMonth: number | null
  teamAvgPreviousMonth: number | null
  vsTeam: VsTeamVerdict
}

export type AdvisorVsTeamComparison = {
  advisor: BrandAdvisorRow
  context: AdvisorTeamContext
  rows: AdvisorPerformanceCompareRow[]
}

const EMPTY_SUMMARY: WonSalesSummary = {
  total_units: 0,
  units_this_month: 0,
  units_previous_month: 0,
  month_over_month_change_pct: null,
  this_month_key: '',
  previous_month_key: '',
}

function advisorId(row: BrandAdvisorRow): string {
  return row.owner_id ?? 'unassigned'
}

function avg(values: number[]): number | null {
  if (values.length === 0) return null
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function emptyPerformance(): GroupPerformanceMetrics {
  return {
    won_sales: { ...EMPTY_SUMMARY },
    leads_created: { ...EMPTY_SUMMARY },
    tasks_overdue: 0,
    tasks_overdue_monthly: { ...EMPTY_SUMMARY },
    tasks_completed_monthly: { ...EMPTY_SUMMARY },
    tasks_managed_monthly: { ...EMPTY_SUMMARY },
    calls_monthly: { ...EMPTY_SUMMARY },
    whatsapp_monthly: { ...EMPTY_SUMMARY },
  }
}

export function advisorPerformance(row: BrandAdvisorRow): GroupPerformanceMetrics {
  if (row.performance) return row.performance

  const base = emptyPerformance()
  base.won_sales = row.won_sales ?? base.won_sales
  base.leads_created = row.leads_created ?? base.leads_created
  base.tasks_overdue = row.tasks_overdue ?? 0
  base.tasks_overdue_monthly = {
    ...base.tasks_overdue_monthly,
    units_this_month: base.tasks_overdue,
  }
  base.calls_monthly = {
    ...base.calls_monthly,
    units_this_month: row.total_calls ?? 0,
  }
  base.whatsapp_monthly = {
    ...base.whatsapp_monthly,
    units_this_month: row.whatsapp_messages ?? 0,
  }
  return base
}

export function resolveAdvisorTeam(
  ownerId: string,
  teams: HubSpotTeamOption[],
): HubSpotTeamOption | null {
  const matches = teams.filter((team) => team.owner_ids.includes(ownerId))
  if (matches.length === 0) return null
  return [...matches].sort(
    (a, b) => b.member_count - a.member_count || a.team_name.localeCompare(b.team_name),
  )[0]
}

export function listCompareReferenceOptions(
  teams: HubSpotTeamOption[],
  groups: AdvisorGroup[],
  brandLabel: string,
): CompareReferenceOption[] {
  const options: CompareReferenceOption[] = []

  for (const team of [...teams].sort(
    (a, b) => b.member_count - a.member_count || a.team_name.localeCompare(b.team_name),
  )) {
    options.push({
      key: `team:${team.team_id}`,
      label: `${team.team_name} · Team HubSpot (${team.member_count})`,
      reference: {
        kind: 'team',
        id: team.team_id,
        name: team.team_name,
        ownerIds: team.owner_ids,
      },
    })
  }

  for (const group of [...groups].sort(
    (a, b) => b.member_count - a.member_count || a.name.localeCompare(b.name),
  )) {
    options.push({
      key: `group:${group.id}`,
      label: `${group.name} · Grupo guardado (${group.member_count})`,
      reference: {
        kind: 'group',
        id: group.id,
        name: group.name,
        ownerIds: group.members.map((member) => member.owner_id),
      },
    })
  }

  options.push({
    key: 'brand',
    label: `Toda la marca · ${brandLabel}`,
    reference: { kind: 'brand', name: `Todos los asesores · ${brandLabel}` },
  })

  return options
}

export function defaultCompareReferenceKey(
  ownerId: string,
  teams: HubSpotTeamOption[],
  groups: AdvisorGroup[],
): string {
  const advisorTeams = teams.filter((team) => team.owner_ids.includes(ownerId))
  if (advisorTeams.length > 0) {
    const best = [...advisorTeams].sort(
      (a, b) => b.member_count - a.member_count || a.team_name.localeCompare(b.team_name),
    )[0]
    return `team:${best.team_id}`
  }

  const advisorGroups = groups.filter((group) =>
    group.members.some((member) => member.owner_id === ownerId),
  )
  if (advisorGroups.length > 0) {
    const best = [...advisorGroups].sort(
      (a, b) => b.member_count - a.member_count || a.name.localeCompare(b.name),
    )[0]
    return `group:${best.id}`
  }

  return 'brand'
}

export function resolveCompareReference(
  referenceKey: string,
  options: CompareReferenceOption[],
): CompareReference | null {
  return options.find((option) => option.key === referenceKey)?.reference ?? null
}

export function getComparisonContext(
  advisor: BrandAdvisorRow,
  allAdvisors: BrandAdvisorRow[],
  reference: CompareReference,
): AdvisorTeamContext {
  const ownerId = advisorId(advisor)
  const advisorIdsInBrand = new Set(allAdvisors.map(advisorId))

  if (reference.kind === 'brand') {
    const peerOwnerIds = allAdvisors
      .map(advisorId)
      .filter((id) => id !== ownerId && id !== 'unassigned')
    return {
      teamId: null,
      teamName: reference.name,
      peerCount: peerOwnerIds.length,
      peerOwnerIds,
      referenceKind: 'brand',
    }
  }

  const peerOwnerIds = reference.ownerIds.filter(
    (id) => id !== ownerId && advisorIdsInBrand.has(id),
  )

  return {
    teamId: reference.id,
    teamName: reference.name,
    peerCount: peerOwnerIds.length,
    peerOwnerIds,
    referenceKind: reference.kind,
  }
}

/** @deprecated Usar getComparisonContext con referencia explícita. */
export function getPeerAdvisors(
  advisor: BrandAdvisorRow,
  allAdvisors: BrandAdvisorRow[],
  teams: HubSpotTeamOption[],
): AdvisorTeamContext {
  const ownerId = advisorId(advisor)
  const team = resolveAdvisorTeam(ownerId, teams)
  if (team) {
    return getComparisonContext(advisor, allAdvisors, {
      kind: 'team',
      id: team.team_id,
      name: team.team_name,
      ownerIds: team.owner_ids,
    })
  }
  return getComparisonContext(advisor, allAdvisors, {
    kind: 'brand',
    name: 'Todos los asesores de la marca',
  })
}

export function classifyVsTeam(
  advisorValue: number,
  teamAvg: number | null,
  higherIsBetter: boolean,
  tolerancePct = 10,
): VsTeamVerdict {
  if (teamAvg == null) return null
  if (teamAvg === 0) {
    if (advisorValue === 0) return 'similar'
    const above = advisorValue > 0
    return higherIsBetter ? (above ? 'above' : 'below') : above ? 'below' : 'above'
  }
  const deltaPct = ((advisorValue - teamAvg) / Math.abs(teamAvg)) * 100
  if (Math.abs(deltaPct) <= tolerancePct) return 'similar'
  const above = advisorValue > teamAvg
  if (higherIsBetter) return above ? 'above' : 'below'
  return above ? 'below' : 'above'
}

export function vsTeamLabel(verdict: VsTeamVerdict): string {
  if (verdict == null) return '—'
  if (verdict === 'similar') return 'Similar al grupo'
  if (verdict === 'above') return 'Por encima del grupo'
  return 'Por debajo del grupo'
}

type PerformanceMetricDef = {
  key: string
  label: string
  higherIsBetter: boolean
  variant?: AdvisorPerformanceCompareRow['variant']
  pick: (perf: GroupPerformanceMetrics) => {
    thisMonth: number
    previousMonth: number
    mom: WonSalesSummary
  }
}

function avgMomPct(values: Array<number | null | undefined>): number | null {
  const valid = values.filter((v): v is number => v != null && !Number.isNaN(v))
  if (valid.length === 0) return null
  return Math.round((valid.reduce((sum, v) => sum + v, 0) / valid.length) * 10) / 10
}

function performanceMetricDefs(): PerformanceMetricDef[] {
  return [
    {
      key: 'won_sales_total',
      label: 'Ventas totales',
      higherIsBetter: true,
      variant: 'total',
      pick: (p) => ({
        thisMonth: p.won_sales.total_units,
        previousMonth: 0,
        mom: p.won_sales,
      }),
    },
    {
      key: 'won_sales_month',
      label: 'Ventas este mes',
      higherIsBetter: true,
      variant: 'month',
      pick: (p) => ({
        thisMonth: p.won_sales.units_this_month,
        previousMonth: p.won_sales.units_previous_month,
        mom: p.won_sales,
      }),
    },
    {
      key: 'won_sales_mom',
      label: 'Cambio mensual ventas',
      higherIsBetter: true,
      variant: 'mom',
      pick: (p) => ({
        thisMonth: p.won_sales.units_this_month,
        previousMonth: p.won_sales.units_previous_month,
        mom: p.won_sales,
      }),
    },
    {
      key: 'leads_created',
      label: 'Leads creados (mes)',
      higherIsBetter: true,
      pick: (p) => ({
        thisMonth: p.leads_created.units_this_month,
        previousMonth: p.leads_created.units_previous_month,
        mom: p.leads_created,
      }),
    },
    {
      key: 'tasks_completed_monthly',
      label: 'Tareas completadas (mes)',
      higherIsBetter: true,
      pick: (p) => ({
        thisMonth: p.tasks_completed_monthly.units_this_month,
        previousMonth: p.tasks_completed_monthly.units_previous_month,
        mom: p.tasks_completed_monthly,
      }),
    },
    {
      key: 'tasks_managed_monthly',
      label: 'Tareas gestionadas (mes)',
      higherIsBetter: true,
      pick: (p) => ({
        thisMonth: p.tasks_managed_monthly.units_this_month,
        previousMonth: p.tasks_managed_monthly.units_previous_month,
        mom: p.tasks_managed_monthly,
      }),
    },
    {
      key: 'tasks_overdue',
      label: 'Tareas atrasadas',
      higherIsBetter: false,
      pick: (p) => ({
        thisMonth: p.tasks_overdue,
        previousMonth: p.tasks_overdue_monthly.units_previous_month,
        mom: {
          ...p.tasks_overdue_monthly,
          units_this_month: p.tasks_overdue,
          units_previous_month: p.tasks_overdue_monthly.units_previous_month,
        },
      }),
    },
    {
      key: 'calls_monthly',
      label: 'Llamadas (mes)',
      higherIsBetter: true,
      pick: (p) => ({
        thisMonth: p.calls_monthly.units_this_month,
        previousMonth: p.calls_monthly.units_previous_month,
        mom: p.calls_monthly,
      }),
    },
    {
      key: 'whatsapp_monthly',
      label: 'WhatsApp (mes)',
      higherIsBetter: true,
      pick: (p) => ({
        thisMonth: p.whatsapp_monthly.units_this_month,
        previousMonth: p.whatsapp_monthly.units_previous_month,
        mom: p.whatsapp_monthly,
      }),
    },
  ]
}

export function buildAdvisorVsTeamComparison(
  advisor: BrandAdvisorRow,
  allAdvisors: BrandAdvisorRow[],
  reference: CompareReference,
): AdvisorVsTeamComparison {
  const context = getComparisonContext(advisor, allAdvisors, reference)
  const peerSet = new Set(context.peerOwnerIds)
  const peers = allAdvisors.filter((row) => peerSet.has(advisorId(row)))
  const advisorPerf = advisorPerformance(advisor)

  const rows: AdvisorPerformanceCompareRow[] = performanceMetricDefs().map((def) => {
    const advisorValues = def.pick(advisorPerf)
    const peerThisMonth = peers.map((peer) => def.pick(advisorPerformance(peer)).thisMonth)
    const peerPreviousMonth = peers.map((peer) => def.pick(advisorPerformance(peer)).previousMonth)
    const teamAvgThisMonth = avg(peerThisMonth)
    const teamAvgPreviousMonth = avg(peerPreviousMonth)
    const roundedTeamAvg =
      teamAvgThisMonth != null ? Math.round(teamAvgThisMonth * 10) / 10 : null

    const teamMomAvg =
      def.variant === 'mom'
        ? avgMomPct(peers.map((peer) => advisorPerformance(peer).won_sales.month_over_month_change_pct))
        : null

    return {
      key: def.key,
      label: def.label,
      higherIsBetter: def.higherIsBetter,
      variant: def.variant,
      advisorThisMonth: advisorValues.thisMonth,
      advisorPreviousMonth: advisorValues.previousMonth,
      advisorMom: advisorValues.mom,
      teamAvgThisMonth: def.variant === 'mom' ? teamMomAvg : roundedTeamAvg,
      teamAvgPreviousMonth:
        teamAvgPreviousMonth != null ? Math.round(teamAvgPreviousMonth * 10) / 10 : null,
      vsTeam:
        def.variant === 'mom'
          ? null
          : classifyVsTeam(advisorValues.thisMonth, roundedTeamAvg, def.higherIsBetter),
    }
  })

  return { advisor, context, rows }
}
