import { describe, expect, it } from 'vitest'
import {
  advisorPerformance,
  buildAdvisorVsTeamComparison,
  classifyVsTeam,
  defaultCompareReferenceKey,
  getComparisonContext,
  getPeerAdvisors,
  listCompareReferenceOptions,
  resolveAdvisorTeam,
  vsTeamLabel,
} from '@/lib/advisorTeamCompare'
import type { BrandAdvisorRow } from '@/types/dealAnalytics'
import type { AdvisorGroup, GroupPerformanceMetrics, HubSpotTeamOption } from '@/types/advisorGroups'

function summary(thisMonth: number, previousMonth: number) {
  return {
    total_units: thisMonth + previousMonth,
    units_this_month: thisMonth,
    units_previous_month: previousMonth,
    month_over_month_change_pct: previousMonth === 0 ? (thisMonth === 0 ? 0 : null) : 50,
    this_month_key: '2026-06',
    previous_month_key: '2026-05',
  }
}

function performance(overrides: Partial<GroupPerformanceMetrics> = {}) {
  return {
    won_sales: summary(2, 1),
    leads_created: summary(5, 4),
    tasks_overdue: 3,
    tasks_overdue_monthly: summary(3, 2),
    tasks_completed_monthly: summary(6, 4),
    tasks_managed_monthly: summary(9, 7),
    calls_monthly: summary(10, 8),
    whatsapp_monthly: summary(20, 15),
    ...overrides,
  }
}

function advisor(ownerId: string, name: string, perfOverrides?: Partial<GroupPerformanceMetrics>, rowOverrides?: Partial<BrandAdvisorRow>): BrandAdvisorRow {
  const perf = performance(perfOverrides)
  return {
    owner_id: ownerId,
    owner_name: name,
    brand_value: 'shacman',
    assigned_deals: 10,
    open_deals: 10,
    new_deals_7d: 1,
    new_deals_30d: 3,
    stale_45d_open: 2,
    tasks_completed: 5,
    tasks_open: 2,
    tasks_overdue: 1,
    deals_with_overdue_tasks: 1,
    managed_30d: 8,
    managed_30d_rate: 0.8,
    tasks_overdue_rate: 0.1,
    won_sales: perf.won_sales,
    leads_created: perf.leads_created,
    performance: perf,
    ...rowOverrides,
  }
}

const teams: HubSpotTeamOption[] = [
  {
    team_id: 't1',
    team_name: 'FONTANAR',
    member_count: 3,
    owner_ids: ['a1', 'a2', 'a3'],
  },
  {
    team_id: 't2',
    team_name: 'LA COLINA',
    member_count: 2,
    owner_ids: ['a4', 'a5'],
  },
]

const groups: AdvisorGroup[] = [
  {
    id: 'g1',
    name: 'FONTANAR',
    description: null,
    brand_value: 'shacman',
    source: 'hubspot_team',
    hubspot_source_id: 't1',
    hubspot_source_label: 'FONTANAR',
    members: [
      { owner_id: 'a1', owner_name: 'Ana' },
      { owner_id: 'a2', owner_name: 'Bob' },
    ],
    member_count: 2,
    created_at: null,
    updated_at: null,
  },
]

describe('resolveAdvisorTeam', () => {
  it('returns the largest team containing the advisor', () => {
    expect(resolveAdvisorTeam('a2', teams)?.team_name).toBe('FONTANAR')
  })

  it('returns null when advisor has no team', () => {
    expect(resolveAdvisorTeam('unknown', teams)).toBeNull()
  })
})

describe('listCompareReferenceOptions', () => {
  it('includes teams, groups and brand fallback', () => {
    const options = listCompareReferenceOptions(teams, groups, 'Shacman')
    expect(options.some((o) => o.key === 'team:t1')).toBe(true)
    expect(options.some((o) => o.key === 'group:g1')).toBe(true)
    expect(options.some((o) => o.key === 'brand')).toBe(true)
  })
})

describe('defaultCompareReferenceKey', () => {
  it('prefers hubspot team for advisor', () => {
    expect(defaultCompareReferenceKey('a2', teams, groups)).toBe('team:t1')
  })

  it('falls back to brand when no team or group', () => {
    expect(defaultCompareReferenceKey('x9', teams, groups)).toBe('brand')
  })
})

describe('getComparisonContext', () => {
  it('uses selected team peers with cartera in marca', () => {
    const all = [advisor('a1', 'Ana'), advisor('a4', 'Dan'), advisor('a5', 'Eve')]
    const context = getComparisonContext(all[0], all, {
      kind: 'team',
      id: 't2',
      name: 'LA COLINA',
      ownerIds: ['a4', 'a5', 'a1'],
    })
    expect(context.teamName).toBe('LA COLINA')
    expect(context.peerOwnerIds).toEqual(['a4', 'a5'])
  })
})

describe('getPeerAdvisors', () => {
  it('uses hubspot team peers when available', () => {
    const context = getPeerAdvisors(advisor('a1', 'Ana'), [advisor('a1', 'Ana'), advisor('a2', 'Bob')], teams)
    expect(context.teamName).toBe('FONTANAR')
    expect(context.peerOwnerIds).toEqual(['a2'])
  })
})

describe('classifyVsTeam', () => {
  it('marks similar values within tolerance', () => {
    expect(classifyVsTeam(9, 10, true)).toBe('similar')
  })

  it('inverts verdict for lower-is-better metrics', () => {
    expect(classifyVsTeam(2, 5, false)).toBe('above')
    expect(vsTeamLabel('above')).toBe('Por encima del grupo')
  })
})

describe('buildAdvisorVsTeamComparison', () => {
  it('computes team average excluding selected advisor', () => {
    const all = [
      advisor('a1', 'Ana', { won_sales: summary(2, 1) }),
      advisor('a2', 'Bob', { won_sales: summary(4, 2) }),
      advisor('a3', 'Car', { won_sales: summary(6, 3) }),
    ]
    const result = buildAdvisorVsTeamComparison(all[0], all, {
      kind: 'team',
      id: 't1',
      name: 'FONTANAR',
      ownerIds: ['a1', 'a2', 'a3'],
    })
    expect(result.context.peerCount).toBe(2)
    const sales = result.rows.find((row) => row.key === 'won_sales_month')
    expect(sales?.advisorThisMonth).toBe(2)
    expect(sales?.teamAvgThisMonth).toBe(5)
    expect(sales?.vsTeam).toBe('below')
  })

  it('reads performance metrics from advisor rows', () => {
    const row = advisor('a1', 'Ana', undefined, { performance: performance() })
    expect(advisorPerformance(row).calls_monthly.units_this_month).toBe(10)
  })

  it('falls back to won_sales and leads when performance is missing', () => {
    const row = advisor('a1', 'Ana', undefined, {
      performance: undefined,
      won_sales: summary(3, 2),
      leads_created: summary(7, 5),
      tasks_overdue: 4,
    })
    const perf = advisorPerformance(row)
    expect(perf.won_sales.units_this_month).toBe(3)
    expect(perf.leads_created.units_this_month).toBe(7)
    expect(perf.tasks_overdue).toBe(4)
  })
})
